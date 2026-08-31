let img;
function setup(){ createCanvas(600,600,WEBGL); background("#fff");
  img = loadImage("https://upload.wikimedia.org/watercolour.png"); }
function draw(){ image(img,-300,-300,600,600); noLoop(); }
