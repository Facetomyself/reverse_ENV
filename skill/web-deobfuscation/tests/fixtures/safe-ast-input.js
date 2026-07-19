const folded = (1 + 2) * 4;
const object = {
  ["answer"]: folded,
  ["__proto__"]: "data-property"
};
const selected = true ? object["answer"] : 0;
if (false) {
  sideEffect();
} else {
  publish(selected);
}
debugger;
function dormant(code) {
  return eval(code);
}
