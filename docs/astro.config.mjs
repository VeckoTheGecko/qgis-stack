// @ts-check
import { satteri } from "@astrojs/markdown-satteri";
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import { defineHastPlugin } from "satteri";
import starlightLinksValidator from "starlight-links-validator";

// GitHub Pages serves the site from a sub-path (https://<owner>.github.io/<repo>/);
// the docs workflow sets both from actions/configure-pages.
const base = process.env.BASE_PATH || "/";

/**
 * Pages link to each other root-relative (`/guides/getting-started/`). This adds the
 * base path, so the links work under any base. The links validator runs after it and
 * checks the final URLs.
 */
const baseLinks = defineHastPlugin({
  name: "base-links",
  element: {
    filter: ["a"],
    visit(node, ctx) {
      const href = node.properties?.href;
      if (typeof href === "string" && /^\/(?!\/)/.test(href)) {
        ctx.setProperty(node, "href", base.replace(/\/$/, "") + href);
      }
    },
  },
});

export default defineConfig({
  // Unset or empty on pull requests: an empty string is an invalid URL to Astro.
  site: process.env.SITE_URL || undefined,
  base,
  markdown: { processor: satteri({ hastPlugins: [baseLinks] }) },
  integrations: [
    starlight({
      title: "QGIS Stack",
      description:
        "QGIS plugins from plugins.qgis.org as conda packages, for reproducible QGIS setups with pixi.",
      plugins: [starlightLinksValidator()],
      sidebar: [
        {
          label: "Start here",
          items: [
            "guides/getting-started",
            "guides/enabling-plugins",
            "catalogue",
            "guides/requesting-plugins",
            "faq",
          ],
        },
        {
          label: "Background",
          items: [{ autogenerate: { directory: "background" } }],
        },
        {
          label: "Maintainers",
          items: [{ autogenerate: { directory: "maintainers" } }],
        },
      ],
    }),
  ],
});
