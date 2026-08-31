function setup(){
  createCanvas(600,600,WEBGL);
  background("#fcf8f2");
  brush.scaleBrushes(2.5);
  brush.field("seabed");
  brush.noStroke();
  brush.fill("#ef9a80", 150);
  brush.fillBleed(0.42,"out");
  brush.fillTexture(0.62,0.4);
  for (let i=0;i<5;i++){
    const a=i*TWO_PI/5-0.3;
    brush.polygon([[Math.cos(a)*22,Math.sin(a)*22],
                   [Math.cos(a-0.36)*158,Math.sin(a-0.36)*158],
                   [Math.cos(a+0.36)*158,Math.sin(a+0.36)*158]]);
  }
  brush.set("2B","#5e3225",0.8);
  brush.noFill();
  brush.circle(0,0,30,true);
}
