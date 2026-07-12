import { describe, expect, it } from "@rstest/core";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { createMarkdownLinkComponent } from "@/components/workspace/messages/markdown-link";

function renderLink(href: string, label = "订阅截图1") {
  const MarkdownLink = createMarkdownLinkComponent("thread-1");
  return renderToStaticMarkup(createElement(MarkdownLink, { href }, label));
}

describe("MarkdownLink evidence images", () => {
  it("renders trusted Commodity Center image links as clickable previews", () => {
    const href =
      "https://platform-media.meitudata.com/competitor/record/subscribe.png";
    const html = renderLink(href);

    expect(html).toContain(`<img src="${href}"`);
    expect(html).toContain('alt="订阅截图1"');
    expect(html).toContain('loading="lazy"');
    expect(html).toContain('referrerPolicy="no-referrer"');
    expect(html).toContain(`<a href="${href}"`);
  });

  it("keeps ordinary external links as links without image previews", () => {
    const html = renderLink("https://example.com/pricing");

    expect(html).toContain('href="https://example.com/pricing"');
    expect(html).not.toContain("<img");
  });

  it("does not preview image-looking URLs from untrusted hosts", () => {
    const html = renderLink("https://example.com/subscribe.png");

    expect(html).toContain('href="https://example.com/subscribe.png"');
    expect(html).not.toContain("<img");
  });
});
