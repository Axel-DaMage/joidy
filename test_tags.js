const content = "Some text\n#Tag: [[Ejemplo]]\nMore text";
function extractTagsFromContent(text) {
  const regex = /#Tag:\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/gi;
  let match;
  const extracted = new Set();
  while ((match = regex.exec(text)) !== null) {
    extracted.add(match[1].trim().toLowerCase());
  }
  return Array.from(extracted);
}
console.log(extractTagsFromContent(content));

let c2 = content + "\n#Tag: [[Another|Alias]]";
console.log(extractTagsFromContent(c2));

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

let t = "ejemplo";
const regex = new RegExp(`\\n?\\s*#Tag:\\s*\\[\\[${escapeRegExp(t)}(?:\\|[^\\]]+)?\\]\\]`, 'gi');
console.log(c2.replace(regex, ''));
