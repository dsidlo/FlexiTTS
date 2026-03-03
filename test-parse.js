const fs = require('fs');
const { JSDOM } = require('jsdom');

const xml = fs.readFileSync('Story-Entanglement/story-xml/01-Hendrix.xml', 'utf8');
const dom = new JSDOM(xml, { contentType: "text/xml" });
const xmlDoc = dom.window.document;

const dialogNodes = Array.from(xmlDoc.querySelectorAll('dialog, narration'));
console.log(`Found ${dialogNodes.length} nodes.`);

if (dialogNodes.length > 0) {
  const node = dialogNodes[0];
  console.log("Node attributes:", Array.from(node.attributes).map(a => `${a.name}=${a.value}`).join(", "));
  console.log("Node textContent:", node.textContent.trim());
}
