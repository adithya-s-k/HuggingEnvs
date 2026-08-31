function setup(){ createCanvas(600,600,WEBGL); background("#fcf8f2"); brush.scaleBrushes(2.5); }
function draw(){
  brush.field("seabed"); brush.noStroke();
  brush.fill("#ef9a80", 150); brush.fillBleed(0.42,"out"); brush.fillTexture(0.62,0.4);
  for (let i=0;i<5;i++){ const a=i*TWO_PI/5-0.3;
    brush.polygon([[Math.cos(a)*22,Math.sin(a)*22],
                   [Math.cos(a-0.36)*158,Math.sin(a-0.36)*158],
                   [Math.cos(a+0.36)*158,Math.sin(a+0.36)*158]]); }
  brush.fill("#d75f4c", 120); brush.fillBleed(0.3,"in"); brush.fillTexture(0.5,0.5);
  for (let i=0;i<5;i++){ const a=i*TWO_PI/5-0.3;
    brush.polygon([[Math.cos(a)*14,Math.sin(a)*14],
                   [Math.cos(a-0.2)*84,Math.sin(a-0.2)*84],
                   [Math.cos(a+0.2)*84,Math.sin(a+0.2)*84]]); }
  brush.noFill(); brush.set("cpencil","#9c4732",1.0);
  for (let i=0;i<5;i++){ const a=i*TWO_PI/5-0.3;
    brush.spline([[Math.cos(a)*20,Math.sin(a)*20],[Math.cos(a)*92,Math.sin(a)*92],[Math.cos(a)*150,Math.sin(a)*150]],0.6); }
  brush.set("2B","#5e3225",0.8);
  for (let i=0;i<9;i++){ const a=i*TWO_PI/9; brush.line(0,0,Math.cos(a)*36,Math.sin(a)*36-6); }
  brush.noStroke(); brush.fill("#e0b13f",180); brush.fillBleed(0.16,"out"); brush.circle(0,-4,17,true);
  noLoop();
}
