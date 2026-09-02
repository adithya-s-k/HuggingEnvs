function setup(){ createCanvas(600,600,WEBGL); background("#fcf8f2"); brush.scaleBrushes(2); }
function draw(){
  brush.set("marker","#e08a72",1); brush.fill("#e08a72",150); brush.circle(0,-40,80,true);
  textSize(42); fill(0); text("a beautiful watercolour hibiscus", -280, 200);
  noLoop();
}
