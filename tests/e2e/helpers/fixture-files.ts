import path from "path";

export const FIXTURE_DIR = path.join(__dirname, "..", "test-data");

export const fixtures = {
  smallTxt: path.join(FIXTURE_DIR, "small.txt"),
  smallMd: path.join(FIXTURE_DIR, "small.md"),
  smallCsv: path.join(FIXTURE_DIR, "small.csv"),
  smallJson: path.join(FIXTURE_DIR, "small.json"),
  smallPdf: path.join(FIXTURE_DIR, "small.pdf"),
  invalidExtension: path.join(FIXTURE_DIR, "invalid-extension.exe"),
  malformedPdf: path.join(FIXTURE_DIR, "malformed.pdf"),
};

/**
 * Generated in-memory rather than committed to the repo — an oversized
 * fixture has no useful content to review in a diff and would bloat the
 * repository. Used with Playwright's `setInputFiles({ name, mimeType, buffer })`.
 *
 * Capped under 50MB: Playwright's setInputFiles rejects an in-memory buffer
 * larger than that ("Cannot set buffer larger than 50Mb, please write it to
 * a file and pass its path instead"). 45MB is still large enough to probe
 * for a backend size limit without hitting that ceiling.
 */
export function oversizedFilePayload(sizeBytes = 45 * 1024 * 1024) {
  return {
    name: "oversized-fixture.txt",
    mimeType: "text/plain",
    buffer: Buffer.alloc(sizeBytes, "0"),
  };
}

export function emptyFilePayload() {
  return {
    name: "empty-fixture.txt",
    mimeType: "text/plain",
    buffer: Buffer.alloc(0),
  };
}
