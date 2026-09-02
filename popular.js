const fs = require("fs");
const path = require("path");
const { Pool } = require("pg");
const copyFrom = require("pg-copy-streams").from;

// Load .env.local if present and DATABASE_URL is not set
if (!process.env.DATABASE_URL) {
  const envLocalPath = path.join(__dirname, ".env.local");
  if (fs.existsSync(envLocalPath)) {
    const envContent = fs.readFileSync(envLocalPath, "utf-8");
    for (const line of envContent.split("\n")) {
      const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const key = match[1];
        let value = match[2] || "";
        if (value.startsWith('"') && value.endsWith('"')) {
          value = value.slice(1, -1);
        }
        process.env[key] = value.trim();
      }
    }
  }
}

const connection_string = process.env.DATABASE_URL;

const DATASET_DIR = path.join(__dirname, "dataset");

// https://www.kaggle.com/datasets/matteo2002/retail-dataset
const TABLES = [
  {
    file: "customers.csv",
    table: "customers",
    ddl: `
      CREATE TABLE IF NOT EXISTS customers (
        "CustomerID" INTEGER PRIMARY KEY,
        customer_type TEXT NOT NULL
      )
    `,
    upsertQuery: (table, staging) => `
      INSERT INTO ${table} ("CustomerID", customer_type)
      SELECT "CustomerID", customer_type FROM ${staging}
      ON CONFLICT ("CustomerID") DO UPDATE
      SET customer_type = EXCLUDED.customer_type;
    `,
  },
  {
    file: "products.csv",
    table: "products",
    ddl: `
      CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        item TEXT NOT NULL,
        category TEXT NOT NULL,
        price NUMERIC(10, 2) NOT NULL
      )
    `,
    upsertQuery: (table, staging) => `
      INSERT INTO ${table} (product_id, item, category, price)
      SELECT product_id, item, category, price FROM ${staging}
      ON CONFLICT (product_id) DO UPDATE
      SET item = EXCLUDED.item,
          category = EXCLUDED.category,
          price = EXCLUDED.price;
    `,
  },
  {
    file: "purchases.csv",
    table: "purchases",
    ddl: `
      CREATE TABLE IF NOT EXISTS purchases (
        "InvoiceID" BIGINT NOT NULL,
        date DATE NOT NULL,
        "CustomerID" INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_purchases_invoice ON purchases ("InvoiceID");
    `,
    upsertQuery: (table, staging) => `
      DELETE FROM ${table}
      WHERE "InvoiceID" IN (SELECT DISTINCT "InvoiceID" FROM ${staging});

      INSERT INTO ${table} ("InvoiceID", date, "CustomerID", product_id, quantity)
      SELECT "InvoiceID", date, "CustomerID", product_id, quantity FROM ${staging};
    `,
  },
  {
    file: "invoice_items.csv",
    table: "invoice_items",
    ddl: `
      CREATE TABLE IF NOT EXISTS invoice_items (
        "InvoiceID" BIGINT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price NUMERIC(10, 2) NOT NULL,
        line_total NUMERIC(12, 2) NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items ("InvoiceID");
    `,
    upsertQuery: (table, staging) => `
      DELETE FROM ${table}
      WHERE "InvoiceID" IN (SELECT DISTINCT "InvoiceID" FROM ${staging});

      INSERT INTO ${table} ("InvoiceID", product_id, quantity, price, line_total)
      SELECT "InvoiceID", product_id, quantity, price, line_total FROM ${staging};
    `,
  },
  {
    file: "discounts.csv",
    table: "discounts",
    ddl: `
      CREATE TABLE IF NOT EXISTS discounts (
        discount_id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL,
        discount_percentage NUMERIC(5, 2) NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        day_of_week TEXT NOT NULL,
        campaign_name TEXT NOT NULL
      )
    `,
    upsertQuery: (table, staging) => `
      INSERT INTO ${table} (discount_id, product_id, discount_percentage, start_date, end_date, day_of_week, campaign_name)
      SELECT discount_id, product_id, discount_percentage, start_date, end_date, day_of_week, campaign_name FROM ${staging}
      ON CONFLICT (discount_id) DO UPDATE
      SET product_id = EXCLUDED.product_id,
          discount_percentage = EXCLUDED.discount_percentage,
          start_date = EXCLUDED.start_date,
          end_date = EXCLUDED.end_date,
          day_of_week = EXCLUDED.day_of_week,
          campaign_name = EXCLUDED.campaign_name;
    `,
  },
];

function copyCsvToTable(client, tableName, filePath) {
  return new Promise((resolve, reject) => {
    const copyQuery = `COPY ${tableName} FROM STDIN WITH (FORMAT csv, HEADER true)`;
    const stream = client.query(copyFrom(copyQuery));
    const fileStream = fs.createReadStream(filePath);

    fileStream.on("error", reject);
    stream.on("error", reject);
    stream.on("finish", resolve);

    fileStream.pipe(stream);
  });
}

async function uploadTable(client, { file, table, ddl, upsertQuery }) {
  const filePath = path.join(DATASET_DIR, file);

  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  console.log(`Upserting ${file} -> ${table}...`);

  // Ensure table and indexes exist
  await client.query(ddl);

  const stagingTable = `temp_staging_${table}`;

  await client.query("BEGIN");
  try {
    // Create temporary staging table with identical schema
    await client.query(`DROP TABLE IF EXISTS ${stagingTable}`);
    await client.query(
      `CREATE TEMP TABLE ${stagingTable} (LIKE ${table} INCLUDING DEFAULTS)`,
    );

    // Fast bulk copy from CSV to staging table
    await copyCsvToTable(client, stagingTable, filePath);

    // Execute upsert logic
    await client.query(upsertQuery(table, stagingTable));

    // Cleanup temp table
    await client.query(`DROP TABLE IF EXISTS ${stagingTable}`);

    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  }

  const { rows } = await client.query(
    `SELECT COUNT(*)::int AS count FROM ${table}`,
  );
  console.log(
    `  Done: ${rows[0].count.toLocaleString()} rows in ${table}`,
  );
}

async function main() {
  const pool = new Pool({ connectionString: connection_string });
  const client = await pool.connect();

  try {
    console.log("Connected to database.\n");

    for (const tableConfig of TABLES) {
      await uploadTable(client, tableConfig);
    }

    console.log(`\nAll ${TABLES.length} tables upserted successfully.`);
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((error) => {
  console.error("Upload failed:", error.message);
  process.exit(1);
});
