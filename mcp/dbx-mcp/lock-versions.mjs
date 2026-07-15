import fs from "node:fs";

const lockFile = process.argv[2];
if (!lockFile) {
  throw new Error("package-lock.json path is required");
}

const lock = JSON.parse(fs.readFileSync(lockFile, "utf8"));
process.stdout.write(
  JSON.stringify({
    betterSqlite: lock.packages["node_modules/better-sqlite3"]?.version,
    keytar: lock.packages["node_modules/keytar"]?.version,
  }),
);
