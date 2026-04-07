#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const katex = require('katex');
const katexPackage = require('katex/package.json');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');
const KATEX_VERSION = katexPackage.version;
const LOCAL_KATEX_CSS = '/assets/vendor/katex/katex.min.css';

const FILES = [
  {
    path: 'pages/areal.html',
    delimiters: {
      display: [{ left: '$$', right: '$$' }],
      inline: [{ left: '\\(', right: '\\)' }],
    },
  },
  {
    path: 'pages/yarn.html',
    delimiters: {
      display: [{ left: '$$', right: '$$' }],
      inline: [{ left: '$', right: '$' }],
    },
  },
  {
    path: 'pages/diffusion_models.html',
    delimiters: {
      display: [{ left: '$$', right: '$$' }],
      inline: [{ left: '$', right: '$' }],
    },
  },
  {
    path: 'pages/verl_grpo.html',
    delimiters: {
      display: [{ left: '$$', right: '$$' }],
      inline: [{ left: '$', right: '$' }],
    },
  },
  {
    path: 'pages/video_codec.html',
    delimiters: {
      display: [{ left: '$$', right: '$$' }],
      inline: [{ left: '$', right: '$' }],
    },
  },
];

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function removeDir(target) {
  fs.rmSync(target, { recursive: true, force: true });
}

function copyDir(src, dest, skip = new Set()) {
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (skip.has(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath, skip);
    } else if (entry.isFile()) {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function copyKatexAssets() {
  const katexDist = path.join(ROOT, 'node_modules', 'katex', 'dist');
  const targetDir = path.join(DIST, 'assets', 'vendor', 'katex');
  const targetFonts = path.join(targetDir, 'fonts');

  ensureDir(targetFonts);
  fs.copyFileSync(path.join(katexDist, 'katex.min.css'), path.join(targetDir, 'katex.min.css'));

  for (const file of fs.readdirSync(path.join(katexDist, 'fonts'))) {
    fs.copyFileSync(path.join(katexDist, 'fonts', file), path.join(targetFonts, file));
  }
}

function renderLatex(latex, displayMode) {
  return katex.renderToString(latex, {
    displayMode,
    throwOnError: false,
    trust: true,
    strict: false,
  });
}

function normalizeLatex(latex) {
  return latex
    .replace(/\\\\([A-Za-z])/g, '\\$1')
    .replace(/\\\\([(){}\[\]])/g, '\\$1');
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function replaceDelimited(text, left, right, displayMode) {
  const pattern = new RegExp(`${escapeRegex(left)}([\\s\\S]+?)${escapeRegex(right)}`, 'g');
  return text.replace(pattern, (match, latex) => {
    const trimmed = normalizeLatex(latex.trim());
    if (!trimmed) return match;
    return renderLatex(trimmed, displayMode);
  });
}

function replaceInlineDollar(text) {
  return text.replace(/(^|[^$\\])\$(?![${])([^$\n]+?)\$(?!\$)/g, (match, prefix, latex) => {
    const trimmed = normalizeLatex(latex.trim());
    if (!trimmed) return match;
    if (!/[\\{}^_=]|[A-Za-z]+/.test(trimmed)) return match;
    return `${prefix}${renderLatex(trimmed, false)}`;
  });
}

function replaceFormulas(text, config) {
  let output = text;
  for (const { left, right } of config.display) {
    if (left === '$$' && right === '$$') {
      output = replaceDelimited(output, left, right, true);
    }
  }
  for (const { left, right } of config.inline) {
    if (left === '$' && right === '$') {
      output = replaceInlineDollar(output);
    } else {
      output = replaceDelimited(output, left, right, false);
    }
  }
  return output;
}

function removeKatexRuntimeTags(html) {
  return html
    .replace(/\s*<!--\s*KaTeX for math rendering\s*-->\s*/gi, '\n')
    .replace(/\s*<script[^>]*src=["'][^"']*(?:katex\.min\.js|auto-render\.min\.js)[^"']*["'][^>]*><\/script>\s*/gi, '\n')
    .replace(/\s*<script[^>]*src=["'][^"']*(?:katex\.min\.js|auto-render\.min\.js)[^"']*["'][^>]*>\s*<\/script>\s*/gi, '\n');
}

function replaceKatexCssLink(html) {
  return html.replace(/https:\/\/cdn\.jsdelivr\.net\/npm\/katex@[^"']+\/dist\/katex\.min\.css/g, LOCAL_KATEX_CSS);
}

function removeRenderMathCalls(js) {
  return js
    .replace(/\s*if\s*\(\s*typeof\s+renderMathInElement\s*!==?\s*['"](?:undefined|function)['"]\s*\)\s*\{[\s\S]*?renderMathInElement\([\s\S]*?\);?\s*\}/g, '')
    .replace(/\s*if\s*\(\s*typeof\s+renderMathInElement\s*===?\s*['"]function['"]\s*\)\s*\{[\s\S]*?renderMathInElement\([\s\S]*?\);?\s*\}/g, '')
    .replace(/\s*renderMathInElement\s*\(\s*document\.body\s*,\s*\{[\s\S]*?\}\s*\)\s*;?/g, '')
    .replace(/\s*window\.addEventListener\(\s*["']load["']\s*,\s*\(\)\s*=>\s*\{[\s\S]*?renderMathInElement\([\s\S]*?\);?[\s\S]*?\}\s*\)\s*;?/g, '')
    .replace(/\s*document\.addEventListener\(\s*["']DOMContentLoaded["']\s*,\s*function\s*\(\)\s*\{\s*\}\s*\)\s*;?/g, '')
    .replace(/\s*document\.addEventListener\(\s*["']DOMContentLoaded["']\s*,\s*\(\)\s*=>\s*\{\s*\}\s*\)\s*;?/g, '');
}

function transformJsStrings(js, config) {
  return js.replace(/"((?:[^"\\]|\\.)*)"/g, (full, raw) => {
    let decoded;
    try {
      decoded = JSON.parse(`"${raw}"`);
    } catch {
      return full;
    }

    const transformed = replaceFormulas(decoded, config);
    if (transformed === decoded) return full;
    return JSON.stringify(transformed);
  });
}

function transformJsSingleQuoteStrings(js, config) {
  return js.replace(/'((?:[^'\\]|\\.)*)'/g, (full) => {
    let decoded;
    try {
      decoded = Function(`"use strict"; return (${full});`)();
    } catch {
      return full;
    }

    const transformed = replaceFormulas(decoded, config);
    if (transformed === decoded) return full;

    const inner = JSON.stringify(transformed).slice(1, -1).replace(/'/g, "\\'");
    return `'${inner}'`;
  });
}

function transformHtmlFile(relPath, delimiterConfig) {
  const filePath = path.join(DIST, relPath);
  let html = fs.readFileSync(filePath, 'utf8');

  html = removeKatexRuntimeTags(html);
  html = replaceKatexCssLink(html);

  const parts = html.split(/(<script\b[^>]*>[\s\S]*?<\/script>)/gi);
  const out = parts.map((part) => {
    if (!part.toLowerCase().startsWith('<script')) {
      return replaceFormulas(part, delimiterConfig);
    }

    const openTagMatch = part.match(/^<script\b[^>]*>/i);
    const closeTagMatch = part.match(/<\/script>$/i);
    if (!openTagMatch || !closeTagMatch) return part;

    const openTag = openTagMatch[0];
    if (/\bsrc\s*=/.test(openTag)) return part;

    const body = part.slice(openTag.length, part.length - closeTagMatch[0].length);
    const transformed = removeRenderMathCalls(
      transformJsSingleQuoteStrings(transformJsStrings(body, delimiterConfig), delimiterConfig),
    );
    return `${openTag}${transformed}${closeTagMatch[0]}`;
  });

  html = out.join('').replace(/\n{3,}/g, '\n\n');
  fs.writeFileSync(filePath, html);
}

function buildDist() {
  removeDir(DIST);
  copyDir(ROOT, DIST, new Set(['.git', 'node_modules', 'dist', '.playwright-mcp', 'tmp', '.opencode']));
  copyKatexAssets();

  for (const file of FILES) {
    transformHtmlFile(file.path, file.delimiters);
  }
}

function cleanKatexTempFiles() {
  for (const file of ['pages/areal.html.bak', 'pages/yarn.html.bak', 'pages/diffusion_models.html.bak']) {
    const target = path.join(ROOT, file);
    if (fs.existsSync(target)) fs.rmSync(target, { force: true });
  }
}

buildDist();
cleanKatexTempFiles();

console.log(`Built KaTeX-prerendered site into dist/ with local KaTeX ${KATEX_VERSION} assets.`);
