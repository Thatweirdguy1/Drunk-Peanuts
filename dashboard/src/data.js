export const tools = [
  {
    id: "convert",
    name: "Convert",
    description: "A new format. Same possibilities.",
    detail: "Conversion, compression, OCR, PDF, images, media & ZIPs",
    icon: "convert",
    group: "Convert",
  },
  {
    id: "pages",
    name: "Pages",
    description: "Give your ideas a little structure.",
    detail: "Document editing",
    icon: "pages",
    group: "Create",
  },
  {
    id: "tables",
    name: "Tables",
    description: "Make the numbers make sense.",
    detail: "Spreadsheets",
    icon: "tables",
    group: "Create",
  },
  {
    id: "dazzle",
    name: "Dazzle",
    description: "Something worth presenting.",
    detail: "Presentations",
    icon: "dazzle",
    group: "Create",
  },
  {
    id: "sketch",
    name: "Sketch",
    description: "Start with a line. See where it goes.",
    detail: "Drawing",
    icon: "sketch",
    group: "Create",
  },
  {
    id: "organize",
    name: "Organize",
    description: "Find a place for every detail.",
    detail: "Databases",
    icon: "organize",
    group: "Create",
  },
  {
    id: "formulaic",
    name: "Formulaic",
    description: "Work out your next big equation.",
    detail: "Formula editing",
    icon: "formulaic",
    group: "Create",
  },
  {
    id: "writer",
    name: "Writer",
    description: "Every good scene starts somewhere.",
    detail: "Screenplays",
    icon: "writer",
    group: "Create",
  },
  {
    id: "play",
    name: "Play",
    description: "Take a moment. Press play.",
    detail: "Local audio & video",
    icon: "play",
    group: "Play",
  },
];
export const sampleFiles = [
  {
    id: "sample-notes",
    name: "Harbor field notes.docx",
    size: "2.4 MB",
    tool: "pages",
    modified: "12 minutes ago",
    sample: true,
  },
  {
    id: "sample-budget",
    name: "October shoot budget.xlsx",
    size: "48 KB",
    tool: "tables",
    modified: "Yesterday",
    sample: true,
  },
  {
    id: "sample-film",
    name: "Harbor-at-dawn.mp4",
    size: "184 MB",
    tool: "play",
    modified: "Yesterday",
    sample: true,
  },
];
export function filterTools(query, group = "All") {
  const term = query.trim().toLowerCase();
  return tools.filter(
    (tool) =>
      (group === "All" || tool.group === group) &&
      `${tool.name} ${tool.detail}`.toLowerCase().includes(term),
  );
}
export function toolForFile(name) {
  const extension = name.split(".").pop().toLowerCase();
  if (
    ["mp4", "mov", "mkv", "webm", "mp3", "wav", "flac", "ogg"].includes(
      extension,
    )
  )
    return "play";
  if (["docx", "doc", "odt", "txt"].includes(extension)) return "pages";
  if (["xlsx", "xls", "csv", "ods"].includes(extension)) return "tables";
  if (["pptx", "ppt", "odp"].includes(extension)) return "dazzle";
  if (["fountain"].includes(extension)) return "writer";
  return "convert";
}
