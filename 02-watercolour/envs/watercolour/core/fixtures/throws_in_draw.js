// Paints enough to clear the gate's paint floor, then throws before reaching
// noLoop(), so the render is cut off rather than finished. Uses only the ten
// allowed brush methods: the point of this fixture is a runtime error, not a
// rejected API.
async function setup() {
  createCanvas(600, 600, WEBGL);
  brush.scaleBrushes(3);
  angleMode(DEGREES);
}

function draw() {
  translate(-width / 2, -height / 2);
  background("#f9f5f0");

  brush.noStroke();
  brush.fill("#e08a72", 210);
  brush.fillBleed(0.25);
  brush.beginShape(0.6);
  brush.vertex(180, 200);
  brush.vertex(420, 220);
  brush.vertex(380, 430);
  brush.vertex(200, 400);
  brush.endShape(true);

  brush.fill("#d87a64", 220);
  brush.circle(300, 300, 90, 0.3);

  const petals = null;
  brush.circle(300, 300, petals.radius, 0.3);
}
