export async function load(bytes, imports) {
  return WebAssembly.instantiate(bytes, imports);
}
