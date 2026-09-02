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
  brush.fillBleed(0.25);
  brush.fillTexture(0.5, 0.4);

  brush.fill("#6b8f5a", 200);
  brush.beginShape(0);
  brush.vertex(294, 300);
  brush.vertex(306, 300);
  brush.vertex(306, 470);
  brush.vertex(294, 470);
  brush.endShape(true);

  brush.fill("#e08a72", 205);
  for (let a = 0; a < 360; a += 72) {
    brush.beginShape(0.6);
    for (let t = 0; t < 360; t += 60) {
      const r = t < 180 ? 115 : 62;
      brush.vertex(300 + r * cos(a + t), 300 + r * sin(a + t));
    }
    brush.endShape(true);
  }

  brush.fill("#f2c14e", 220);
  brush.circle(300, 300, 34, 0.2);

  brush.fill("#7fa06a", 190);
  brush.circle(248, 424, 40, 0.3);
  brush.circle(352, 444, 36, 0.3);

  brush.noFill();
}
