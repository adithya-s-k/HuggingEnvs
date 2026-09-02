// Calls a brush method that does not exist. The restricted allowlist rejects it
// at the gate, and `inspect_source` reports it in `unknown_calls`, which is what
// tells a training run the model invented an API rather than misused a real one.
async function setup() {
  createCanvas(600, 600, WEBGL);
  brush.scaleBrushes(3);
  angleMode(DEGREES);
  noLoop();
}

function draw() {
  translate(-width / 2, -height / 2);
  background("#f9f5f0");
  brush.noStroke();
  brush.fill("#e08a72", 210);
  brush.circle(300, 300, 120, 0.3);
  brush.noLoop();
}
