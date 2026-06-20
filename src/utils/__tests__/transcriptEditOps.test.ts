import { describe, it, expect } from "vitest";
import type { Segment } from "../transcriptEditOps";
import {
  splitSegment,
  countChanges,
  searchSegments,
  replaceAllInSegments,
} from "../transcriptEditOps";

const seg: Segment = { start: 0, end: 10, speaker: "A", text: "hello world" };

describe("splitSegment", () => {
  it("splits text at the cursor and proportions the timestamp", () => {
    const [a, b] = splitSegment(seg, 5);
    // partA keeps the leading text with trailing whitespace trimmed.
    expect(a.text).toBe("hello");
    // partB takes the remainder with leading whitespace trimmed (real
    // production behaviour uses trimStart — so " world" becomes "world").
    expect(b.text).toBe("world");
    // The proportioned midpoint joins the two halves exactly.
    expect(a.end).toBe(b.start);
    expect(a.start).toBe(0);
    expect(b.end).toBe(10);
    // midpoint = start + duration * (pos / len) = 0 + 10 * (5 / 11)
    expect(a.end).toBeCloseTo(10 * (5 / 11), 10);
  });

  it("marks the second half with the transient _justSplit flag", () => {
    const [, b] = splitSegment(seg, 5);
    expect((b as Segment & { _justSplit?: boolean })._justSplit).toBe(true);
  });

  it("preserves the speaker on both halves", () => {
    const [a, b] = splitSegment(seg, 5);
    expect(a.speaker).toBe("A");
    expect(b.speaker).toBe("A");
  });
});

describe("countChanges", () => {
  it("counts segments whose text changed", () => {
    const orig = [seg];
    const draft = [{ ...seg, text: "changed" }];
    expect(countChanges(orig, draft)).toBe(1);
  });

  it("counts a speaker change", () => {
    expect(countChanges([seg], [{ ...seg, speaker: "B" }])).toBe(1);
  });

  it("returns 0 when nothing changed", () => {
    expect(countChanges([seg], [{ ...seg }])).toBe(0);
  });

  it("accounts for length changes (a split adds a segment)", () => {
    const orig = [seg];
    const draft = [
      { ...seg, text: "hello" },
      { ...seg, text: "world" },
    ];
    // lengthChanged branch: abs(2 - 1) = 1, plus aligned text/speaker diffs
    // for indices that still line up against the original (index 0 changed).
    expect(countChanges(orig, draft)).toBe(2);
  });
});

describe("searchSegments", () => {
  it("returns indices of segments whose text matches (case-insensitive)", () => {
    const segs: Segment[] = [
      { ...seg, text: "Alpha beta" },
      { ...seg, text: "gamma" },
      { ...seg, text: "BETA again" },
    ];
    expect(searchSegments(segs, "beta")).toEqual([0, 2]);
  });

  it("returns an empty array for a blank query", () => {
    expect(searchSegments([seg], "   ")).toEqual([]);
  });
});

describe("replaceAllInSegments", () => {
  it("replaces every occurrence and returns the count", () => {
    const { segments, count } = replaceAllInSegments(
      [{ ...seg, text: "a a a" }],
      "a",
      "b",
    );
    expect(count).toBe(3);
    expect(segments[0].text).toBe("b b b");
  });

  it("is case-insensitive when counting and replacing", () => {
    const { segments, count } = replaceAllInSegments(
      [{ ...seg, text: "Cat cat CAT" }],
      "cat",
      "dog",
    );
    expect(count).toBe(3);
    expect(segments[0].text).toBe("dog dog dog");
  });

  it("returns the original segments and count 0 when nothing matches", () => {
    const input: Segment[] = [{ ...seg, text: "nothing here" }];
    const { segments, count } = replaceAllInSegments(input, "xyz", "abc");
    expect(count).toBe(0);
    expect(segments[0].text).toBe("nothing here");
  });
});
