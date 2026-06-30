export const PRODUCT_DISPLAY_NAME = "美图商业化 aios";
export const PRODUCT_SHORT_MARK = "MT";

const DISPLAY_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bDeerFlow\b/g, PRODUCT_DISPLAY_NAME],
  [/\bDeerflow\b/g, PRODUCT_DISPLAY_NAME],
  [/\bDFlow\b/g, PRODUCT_DISPLAY_NAME],
  [/\bDFLOW\b/g, PRODUCT_DISPLAY_NAME],
  [/\bDeepFlow\b/g, PRODUCT_DISPLAY_NAME],
  [/\bDeflo\b/g, PRODUCT_DISPLAY_NAME],
];

export function brandDisplayText(value: string) {
  return DISPLAY_REPLACEMENTS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    value,
  );
}
