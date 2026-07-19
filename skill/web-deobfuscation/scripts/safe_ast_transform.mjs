#!/usr/bin/env node

import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";


const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REVERSE_ROOT = resolve(SCRIPT_DIR, "..", "..", "..");
const RUNTIME_PACKAGE = resolve(
  REVERSE_ROOT,
  "tools",
  "web-deobfuscation",
  "package.json",
);
const runtimeRequire = createRequire(RUNTIME_PACKAGE);
const parser = runtimeRequire("@babel/parser");
const traverse = runtimeRequire("@babel/traverse").default;
const generate = runtimeRequire("@babel/generator").default;
const t = runtimeRequire("@babel/types");
const runtimePackage = runtimeRequire(RUNTIME_PACKAGE);

const DEFAULT_PASSES = [
  "normalize-computed-properties",
  "fold-static-literals",
  "prune-constant-branches",
];
const PASS_NAMES = new Set([
  ...DEFAULT_PASSES,
  "remove-debugger-statements",
]);
const SYNTAX_PLUGINS = {
  js: [],
  jsx: ["jsx"],
  typescript: ["typescript"],
  "typescript-jsx": ["typescript", "jsx"],
};


function usage() {
  return `Usage:
  node safe_ast_transform.mjs \\
    --input <input.js> --output <output.js> \\
    --parse-before <parse-before.json> --parse-after <parse-after.json> \\
    --report <transform-report.json> \\
    [--passes ${DEFAULT_PASSES.join(",")}] \\
    [--syntax js|jsx|typescript|typescript-jsx]

The tool parses and rewrites syntax only. It never imports or executes the
target source, eval, Function, string timers, VM initializers, or WASM code.`;
}


function parseArgs(argv) {
  const result = { syntax: "js", passes: [...DEFAULT_PASSES] };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") {
      result.help = true;
      continue;
    }
    if (!argument.startsWith("--")) {
      throw new Error(`unexpected argument: ${argument}`);
    }
    const key = argument.slice(2);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`missing value for ${argument}`);
    }
    index += 1;
    if (key === "passes") {
      result.passes = value.split(",").map((item) => item.trim()).filter(Boolean);
    } else if (key === "syntax") {
      result.syntax = value;
    } else if (["input", "output", "parse-before", "parse-after", "report"].includes(key)) {
      result[key] = value;
    } else {
      throw new Error(`unknown option: ${argument}`);
    }
  }
  if (result.help) {
    return result;
  }
  for (const key of ["input", "output", "parse-before", "parse-after", "report"]) {
    if (!result[key]) {
      throw new Error(`--${key} is required`);
    }
  }
  if (!Object.hasOwn(SYNTAX_PLUGINS, result.syntax)) {
    throw new Error(`unsupported --syntax: ${result.syntax}`);
  }
  if (result.passes.length === 0) {
    throw new Error("--passes must contain at least one named safe pass");
  }
  const unknownPasses = result.passes.filter((name) => !PASS_NAMES.has(name));
  if (unknownPasses.length > 0) {
    throw new Error(`unknown or unsafe pass: ${unknownPasses.join(", ")}`);
  }
  if (new Set(result.passes).size !== result.passes.length) {
    throw new Error("--passes must not contain duplicates");
  }
  return result;
}


function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}


function writeJson(path, payload) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(payload, null, 2)}\n`, { encoding: "utf8" });
}


function parserOptions(syntax) {
  return {
    sourceType: "unambiguous",
    allowAwaitOutsideFunction: false,
    allowReturnOutsideFunction: false,
    errorRecovery: false,
    plugins: SYNTAX_PLUGINS[syntax],
  };
}


function countNodes(ast) {
  let count = 0;
  traverse(ast, {
    enter() {
      count += 1;
    },
  });
  return count;
}


function parseReport(ast, source, syntax, raw = Buffer.from(source, "utf8")) {
    return {
    schema_version: 1,
    passed: true,
    parser: "@babel/parser",
    parser_version: runtimePackage.dependencies["@babel/parser"],
    syntax,
    source_type: ast.program.sourceType,
    bytes: raw.length,
    sha256: sha256(raw),
    ast_nodes: countNodes(ast),
  };
}


function inherit(replacement, original) {
  return t.inheritsComments(replacement, original);
}


function validDotProperty(name) {
  return t.isValidIdentifier(name, false);
}


function normalizeComputedProperties(ast) {
  let changes = 0;
  function normalizeMember(path) {
    const { node } = path;
    if (node.computed && t.isStringLiteral(node.property) && validDotProperty(node.property.value)) {
      node.property = t.identifier(node.property.value);
      node.computed = false;
      changes += 1;
    }
  }
  traverse(ast, {
    MemberExpression: normalizeMember,
    OptionalMemberExpression: normalizeMember,
    ObjectProperty(path) {
      const { node } = path;
      if (
        node.computed
        && t.isStringLiteral(node.key)
        && node.key.value !== "__proto__"
        && validDotProperty(node.key.value)
      ) {
        node.key = t.identifier(node.key.value);
        node.computed = false;
        changes += 1;
      }
    },
    ObjectMethod(path) {
      const { node } = path;
      if (
        node.computed
        && t.isStringLiteral(node.key)
        && node.key.value !== "__proto__"
        && validDotProperty(node.key.value)
      ) {
        node.key = t.identifier(node.key.value);
        node.computed = false;
        changes += 1;
      }
    },
  });
  return changes;
}


function primitiveValue(node) {
  if (t.isNumericLiteral(node) || t.isStringLiteral(node) || t.isBooleanLiteral(node)) {
    return { known: true, value: node.value };
  }
  if (t.isNullLiteral(node)) {
    return { known: true, value: null };
  }
  return { known: false, value: undefined };
}


function literalNode(value) {
  if (typeof value === "number") {
    if (!Number.isFinite(value) || Object.is(value, -0)) {
      return null;
    }
    return t.numericLiteral(value);
  }
  if (typeof value === "string") {
    return t.stringLiteral(value);
  }
  if (typeof value === "boolean") {
    return t.booleanLiteral(value);
  }
  if (value === null) {
    return t.nullLiteral();
  }
  return null;
}


function foldBinary(operator, left, right) {
  if (typeof left === "number" && typeof right === "number") {
    switch (operator) {
      case "+": return left + right;
      case "-": return left - right;
      case "*": return left * right;
      case "/": return left / right;
      case "%": return left % right;
      case "**": return left ** right;
      case "<<": return left << right;
      case ">>": return left >> right;
      case ">>>": return left >>> right;
      case "|": return left | right;
      case "&": return left & right;
      case "^": return left ^ right;
      case "<": return left < right;
      case "<=": return left <= right;
      case ">": return left > right;
      case ">=": return left >= right;
      case "===": return left === right;
      case "!==": return left !== right;
      default: return undefined;
    }
  }
  if (typeof left === "string" && typeof right === "string") {
    switch (operator) {
      case "+": return left + right;
      case "<": return left < right;
      case "<=": return left <= right;
      case ">": return left > right;
      case ">=": return left >= right;
      case "===": return left === right;
      case "!==": return left !== right;
      default: return undefined;
    }
  }
  if (operator === "===" || operator === "!==") {
    return operator === "===" ? left === right : left !== right;
  }
  return undefined;
}


function foldStaticLiterals(ast) {
  let changes = 0;
  traverse(ast, {
    UnaryExpression: {
      exit(path) {
        const operand = primitiveValue(path.node.argument);
        if (!operand.known) {
          return;
        }
        let value;
        switch (path.node.operator) {
          case "!": value = !operand.value; break;
          case "+":
            if (typeof operand.value !== "number") return;
            value = +operand.value;
            break;
          case "-":
            if (typeof operand.value !== "number") return;
            value = -operand.value;
            break;
          case "~":
            if (typeof operand.value !== "number") return;
            value = ~operand.value;
            break;
          default: return;
        }
        const replacement = literalNode(value);
        if (replacement) {
          path.replaceWith(inherit(replacement, path.node));
          changes += 1;
        }
      },
    },
    BinaryExpression: {
      exit(path) {
        const left = primitiveValue(path.node.left);
        const right = primitiveValue(path.node.right);
        if (!left.known || !right.known) {
          return;
        }
        const value = foldBinary(path.node.operator, left.value, right.value);
        const replacement = literalNode(value);
        if (replacement) {
          path.replaceWith(inherit(replacement, path.node));
          changes += 1;
        }
      },
    },
  });
  return changes;
}


function pruneConstantBranches(ast) {
  let changes = 0;
  traverse(ast, {
    ConditionalExpression(path) {
      if (!t.isBooleanLiteral(path.node.test)) {
        return;
      }
      const replacement = path.node.test.value ? path.node.consequent : path.node.alternate;
      path.replaceWith(inherit(replacement, path.node));
      changes += 1;
    },
    LogicalExpression(path) {
      if (!t.isBooleanLiteral(path.node.left)) {
        return;
      }
      let replacement = null;
      if (path.node.operator === "&&") {
        replacement = path.node.left.value ? path.node.right : path.node.left;
      } else if (path.node.operator === "||") {
        replacement = path.node.left.value ? path.node.left : path.node.right;
      }
      if (replacement) {
        path.replaceWith(inherit(replacement, path.node));
        changes += 1;
      }
    },
    IfStatement(path) {
      if (!t.isBooleanLiteral(path.node.test)) {
        return;
      }
      const replacement = path.node.test.value ? path.node.consequent : path.node.alternate;
      if (replacement) {
        path.replaceWith(inherit(replacement, path.node));
      } else {
        path.remove();
      }
      changes += 1;
    },
  });
  return changes;
}


function removeDebuggerStatements(ast) {
  let changes = 0;
  traverse(ast, {
    DebuggerStatement(path) {
      path.remove();
      changes += 1;
    },
  });
  return changes;
}


function inventoryUnsafeConstructs(ast) {
  const counts = {
    direct_eval: 0,
    function_constructor: 0,
    string_timer: 0,
  };
  traverse(ast, {
    CallExpression(path) {
      const { callee, arguments: args } = path.node;
      if (t.isIdentifier(callee, { name: "eval" })) {
        counts.direct_eval += 1;
      }
      if (t.isIdentifier(callee, { name: "Function" })) {
        counts.function_constructor += 1;
      }
      if (
        t.isIdentifier(callee)
        && ["setTimeout", "setInterval"].includes(callee.name)
        && t.isStringLiteral(args[0])
      ) {
        counts.string_timer += 1;
      }
    },
    NewExpression(path) {
      if (t.isIdentifier(path.node.callee, { name: "Function" })) {
        counts.function_constructor += 1;
      }
    },
  });
  return counts;
}


const PASS_RUNNERS = {
  "normalize-computed-properties": normalizeComputedProperties,
  "fold-static-literals": foldStaticLiterals,
  "prune-constant-branches": pruneConstantBranches,
  "remove-debugger-statements": removeDebuggerStatements,
};


function main(argv) {
  const args = parseArgs(argv);
  if (args.help) {
    process.stdout.write(`${usage()}\n`);
    return 0;
  }
  const paths = {
    input: resolve(args.input),
    output: resolve(args.output),
    parseBefore: resolve(args["parse-before"]),
    parseAfter: resolve(args["parse-after"]),
    report: resolve(args.report),
  };
  const outputPaths = [paths.output, paths.parseBefore, paths.parseAfter, paths.report];
  if (new Set(outputPaths).size !== outputPaths.length) {
    throw new Error("output/report paths must be distinct");
  }
  if (outputPaths.includes(paths.input)) {
    throw new Error("refusing to overwrite the input snapshot");
  }

  const inputBuffer = readFileSync(paths.input);
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const inputSource = decoder.decode(inputBuffer);
  const options = parserOptions(args.syntax);
  let ast;
  try {
    ast = parser.parse(inputSource, options);
  } catch (error) {
    writeJson(paths.parseBefore, {
      schema_version: 1,
      passed: false,
      parser: "@babel/parser",
      syntax: args.syntax,
      error: String(error.message || error),
    });
    return 2;
  }
  const before = parseReport(ast, inputSource, args.syntax, inputBuffer);
  const unsafeConstructs = inventoryUnsafeConstructs(ast);
  const passResults = args.passes.map((name) => ({
    name,
    changes: PASS_RUNNERS[name](ast),
  }));
  const generated = generate(
    ast,
    {
      comments: true,
      compact: false,
      concise: false,
      retainLines: false,
      jsescOption: { minimal: true },
    },
    inputSource,
  ).code + "\n";

  let outputAst;
  try {
    outputAst = parser.parse(generated, options);
  } catch (error) {
    writeJson(paths.parseAfter, {
      schema_version: 1,
      passed: false,
      parser: "@babel/parser",
      syntax: args.syntax,
      error: String(error.message || error),
    });
    return 3;
  }
  const after = parseReport(outputAst, generated, args.syntax);
  const report = {
    schema_version: 1,
    tool: "safe_ast_transform.mjs",
    runtime: {
      node: process.version,
      executable: process.execPath,
      dependency_root: "tools/web-deobfuscation",
      babel: runtimePackage.dependencies,
    },
    input_sha256: before.sha256,
    output_sha256: after.sha256,
    applied_passes: args.passes,
    unsafe_passes: [],
    pass_results: passResults,
    unsafe_constructs_detected: unsafeConstructs,
    target_code_executed: false,
    dynamic_evaluation_used: false,
  };

  mkdirSync(dirname(paths.output), { recursive: true });
  writeFileSync(paths.output, generated, { encoding: "utf8" });
  writeJson(paths.parseBefore, before);
  writeJson(paths.parseAfter, after);
  writeJson(paths.report, report);
  process.stdout.write(`${JSON.stringify({ ok: true, ...report })}\n`);
  return 0;
}


try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  process.stderr.write(`${JSON.stringify({ ok: false, error: String(error.message || error) })}\n`);
  process.exitCode = 1;
}
