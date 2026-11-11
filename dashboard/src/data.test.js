import test from "node:test";
import assert from "node:assert/strict";
import { filterTools, toolForFile, tools } from "./data.js";
test("tool search, category filtering and file routing use supported workspaces", () => {
  assert.equal(tools.length, 9);
  assert.equal(filterTools(" OCR ")[0].id, "convert");
  assert.equal(filterTools("database", "Create")[0].id, "organize");
  assert.deepEqual(filterTools("media", "Create"), []);
  assert.equal(toolForFile("Harbor.MP4"), "play");
  assert.equal(toolForFile("Budget.xlsx"), "tables");
  for (const name of ["Template.potx", "Show.ppsx", "Legacy.ppt", "Open.odp", "Project.dazzle"]) assert.equal(toolForFile(name), "dazzle");
  assert.equal(toolForFile("notes.docx"), "pages");
  assert.equal(toolForFile("script.fountain"), "writer");
  assert.equal(toolForFile("poster.png"), "convert");
});
