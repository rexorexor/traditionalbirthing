const fs = require("fs");
const path = require("path");

module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({ "src/assets": "." });

  // Guards: never render a page silently without stylesheets/fonts.
  eleventyConfig.addNunjucksFilter("csssetOrFail", (v) => {
    if (!Array.isArray(v) || v.length === 0) {
      throw new Error("[head.njk] cssSet missing/unknown or csssets[cssSet] empty — refusing to build a page without stylesheets");
    }
    return v;
  });
  eleventyConfig.addNunjucksFilter("fontblockOrFail", (v) => {
    if (typeof v !== "string" || !v.includes("@font-face")) {
      throw new Error("[head.njk] fontblocks[cssSet] missing — refusing to build a page without @font-face");
    }
    return v;
  });

  eleventyConfig.addNunjucksFilter("getSections", (dir) => {
    const base = path.join(__dirname, "src/_includes/sections", dir);
    if (!fs.existsSync(base)) return [];
    return fs.readdirSync(base)
      .filter((f) => /^section-\d+/.test(f))
      .sort()
      .map((f) => "sections/" + dir + "/" + f.replace(/\.njk$/, ""));
  });

  return {
    dir: { input: "src", includes: "_includes", data: "_data", output: "site" },
    markdownTemplateEngine: "njk",
    templateFormats: ["md", "njk"],
  };
};
