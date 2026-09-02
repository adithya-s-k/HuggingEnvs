function setup(){ createCanvas(600,600,WEBGL); background("#fcf8f2"); brush.scaleBrushes(2); }
function draw(){
  brush.set("marker","#e08a72",1); brush.fill("#e08a72",150);
  for (let i=0;i<5;i++){ const a=i*TWO_PI/5;
