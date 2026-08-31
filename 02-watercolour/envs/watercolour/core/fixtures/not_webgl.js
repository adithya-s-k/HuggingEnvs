function setup(){ createCanvas(600,600); background("#fcf8f2"); brush.scaleBrushes(2); }
function draw(){ brush.set("marker","#e08a72",1); brush.fill("#e08a72",150); brush.circle(0,0,90,true); noLoop(); }
