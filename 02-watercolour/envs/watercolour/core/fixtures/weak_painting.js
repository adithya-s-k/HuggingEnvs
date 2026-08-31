function setup() {
  createCanvas(600, 600, WEBGL);
  background("#f0f8e8");
  brush.scaleBrushes(1.5);
}

function draw() {
  brush.set("charcoal", "#5d4037", 6);
  brush.pick("charcoal");
  brush.strokeWeight(8);
  brush.noFill();
  brush.field("waves");
  brush.flowLine(0, 0, 150, 30);
  brush.flowLine(0, 0, 100, -60);
  brush.flowLine(-100, 0, 120, 45);
  brush.flowLine(100, 0, 90, -30);
  
  brush.set("2B", "#3a2a1d", 4);
  brush.pick("2B");
  brush.strokeWeight(3);
  brush.wash("#c8a88b", 0.4);
  brush.circle(0, 0, 30, true);
  brush.circle(0, 0, 15, true);
  
  brush.set("pen", "#8b7355", 2);
  brush.pick("pen");
  brush.strokeWeight(1);
  brush.line(0, 0, 50, 20);
  brush.line(0, 0, -50, 15);
  brush.line(0, 0, 30, -40);
  brush.line(0, 0, -30, -30);
  
  brush.set("spray", "#e0b08a", 5);
  brush.pick("spray");
  brush.strokeWeight(1);
  brush.wash("#d9c4a3", 0.3);
  brush.hatch(30, 45, {rand: true});
  
  noLoop();
}