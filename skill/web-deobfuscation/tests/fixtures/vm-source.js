const bytecode = new Uint8Array([1, 2, 255]);
let opcodeIndex = 0;
while (true) {
  const opcode = bytecode[opcodeIndex++];
  switch (opcode) {
    case 1:
      break;
    default:
      throw new Error("stop");
  }
}
