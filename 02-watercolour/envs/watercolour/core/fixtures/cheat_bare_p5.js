function setup(){ createCanvas(600,600,WEBGL); background("#fcf8f2"); }
function draw(){
  noStroke(); fill(240,150,130,120);
  for (let i=0;i<5;i++){ const a=i*TWO_PI/5; ellipse(Math.cos(a)*90,Math.sin(a)*90,150,110); }
  fill(230,180,60,180); ellipse(0,0,40,40);
  noLoop();
}
