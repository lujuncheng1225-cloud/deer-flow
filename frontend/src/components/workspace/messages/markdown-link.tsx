import type { AnchorHTMLAttributes } from "react";

import { resolveArtifactURL } from "@/core/artifacts/utils";
import { cn } from "@/lib/utils";

import { CitationLink } from "../citations/citation-link";

function isExternalUrl(href: string | undefined): boolean {
  return !!href && /^https?:\/\//.test(href);
}

const TRUSTED_EVIDENCE_IMAGE_HOSTS = new Set(["platform-media.meitudata.com"]);
const EVIDENCE_IMAGE_PATH_PATTERN = /\.(?:avif|gif|jpe?g|png|webp)$/i;

function isTrustedEvidenceImageUrl(href: string | undefined): boolean {
  if (!href) return false;

  try {
    const url = new URL(href);
    return (
      url.protocol === "https:" &&
      TRUSTED_EVIDENCE_IMAGE_HOSTS.has(url.hostname) &&
      EVIDENCE_IMAGE_PATH_PATTERN.test(url.pathname)
    );
  } catch {
    return false;
  }
}

/**
 * Builds the `a` renderer shared by message content and generic markdown.
 * Passing a `threadId` also resolves `/mnt/` artifact links; without it those
 * links fall through to the default external-link handling.
 */
export function createMarkdownLinkComponent(threadId?: string) {
  return function MarkdownLink({
    href,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement>) {
    if (typeof props.children === "string") {
      const match = /^citation:(.+)$/.exec(props.children);
      if (match) {
        const [, text] = match;
        return (
          <CitationLink {...props} href={href}>
            {text}
          </CitationLink>
        );
      }
    }
    if (href && isTrustedEvidenceImageUrl(href)) {
      const { children, className, target, rel, ...rest } = props;
      const label = typeof children === "string" ? children : "证据截图";
      return (
        <span className={cn("my-3 block max-w-3xl", className)}>
          <a
            {...rest}
            href={href}
            target={target ?? "_blank"}
            rel={rel ?? "noopener noreferrer"}
            className="bg-muted/20 block overflow-hidden rounded-md border"
          >
            <img
              src={href}
              alt={label}
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
              className="max-h-[32rem] w-full object-contain"
            />
          </a>
          <span className="text-muted-foreground mt-1 block text-xs">
            {children}
          </span>
        </span>
      );
    }
    if (threadId && href?.startsWith("/mnt/")) {
      return (
        <a
          {...props}
          href={resolveArtifactURL(href, threadId)}
          target="_blank"
          rel="noopener noreferrer"
        />
      );
    }
    const { className, target, rel, ...rest } = props;
    const external = isExternalUrl(href);
    return (
      <a
        {...rest}
        href={href}
        className={cn(
          "text-primary decoration-primary/30 hover:decoration-primary/60 underline underline-offset-2 transition-colors",
          className,
        )}
        target={target ?? (external ? "_blank" : undefined)}
        rel={rel ?? (external ? "noopener noreferrer" : undefined)}
      />
    );
  };
}
