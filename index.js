const fs = require("fs");
const path = require("path");
const { Pool } = require("pg");
const copyFrom = require("pg-copy-streams").from;

const connection_string = process.env.DATABASE_URL;

const DATASET_DIR = path.join(__dirname, "dataset");

// https://www.kaggle.com/datasets/matteo2002/retail-dataset
const TABLES = [
  {
    file: "customers.csv",
    table: "customers",
    ddl: `
      CREATE TABLE customers (
        "CustomerID" INTEGER PRIMARY KEY,
        customer_type TEXT NOT NULL
        )
        `,
  },
  {
    file: "products.csv",
    table: "products",
    ddl: `
      CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        item TEXT NOT NULL,
        category TEXT NOT NULL,
        price NUMERIC(10, 2) NOT NULL
      )
    `,
  },
  {
    file: "purchases.csv",
    table: "purchases",
    ddl: `
      CREATE TABLE purchases (
        "InvoiceID" BIGINT NOT NULL,
        date DATE NOT NULL,
        "CustomerID" INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL
      )
      `,
  },
  {
    file: "invoice_items.csv",
    table: "invoice_items",
    ddl: `
      CREATE TABLE invoice_items (
        "InvoiceID" BIGINT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price NUMERIC(10, 2) NOT NULL,
        line_total NUMERIC(12, 2) NOT NULL
        )
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

async function uploadTable(client, { file, table, ddl }) {
  const filePath = path.join(DATASET_DIR, file);

  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  console.log(`Uploading ${file} -> ${table}...`);

  await client.query(`DROP TABLE IF EXISTS ${table} CASCADE`);
  await client.query(ddl);

  await copyCsvToTable(client, table, filePath);

  const { rows } = await client.query(
    `SELECT COUNT(*)::int AS count FROM ${table}`,
  );
  console.log(
    `  Done: ${rows[0].count.toLocaleString()} rows loaded into ${table}`,
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

    console.log("\nAll 4 tables uploaded successfully.");
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((error) => {
  console.error("Upload failed:", error.message);
  process.exit(1);
});
