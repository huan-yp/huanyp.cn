#!/usr/bin/env node
'use strict';

const prompts = require('prompts');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const POSTS_DIR = path.join(__dirname, '..', 'source', '_posts');

const CATEGORIES = {
  '技术':     { dir: '技术',     subs: ['基础知识', '软件设计', 'AI 工具', '生产工具', '开源项目', '日志'] },
  '生活':     { dir: '生活',     subs: [] },
  '算法竞赛': { dir: '算法竞赛', subs: ['算法', '题解', '比赛', '代码技巧', '考试总结'] },
  '学习':     { dir: '学习',     subs: ['笔记', '资料', '工具'] },
};

const COMMON_TAGS = [
  '算法竞赛', '题解', '技术', '数学', 'CF', 'C++',
  '生活', '随笔', '动态规划', '代码技巧', 'Python', 'AI',
];

function formatDate(d) {
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function buildFrontmatter({ title, category, tags, date }) {
  let fm = '---\n';
  fm += `title: ${title}\n`;
  fm += `categories:\n  - ${category}\n`;
  if (tags.length) {
    fm += 'tags:\n';
    tags.forEach(t => { fm += `  - ${t}\n`; });
  }
  fm += `date: ${date}\n`;
  fm += '---\n';
  return fm;
}

async function main() {
  const onCancel = () => { process.exit(0); };

  const { title } = await prompts({
    type: 'text',
    name: 'title',
    message: '文章标题',
    validate: v => v.trim() ? true : '标题不能为空',
  }, { onCancel });

  const categoryNames = Object.keys(CATEGORIES);
  const { category } = await prompts({
    type: 'select',
    name: 'category',
    message: '分类',
    choices: categoryNames.map(c => ({ title: c, value: c })),
  }, { onCancel });

  let subcategory = null;
  const subs = CATEGORIES[category].subs;
  if (subs.length > 0) {
    const { sub } = await prompts({
      type: 'select',
      name: 'sub',
      message: '子分类',
      choices: [{ title: '(无)', value: '' }, ...subs.map(s => ({ title: s, value: s }))],
    }, { onCancel });
    subcategory = sub || null;
  }

  const { tagsInput } = await prompts({
    type: 'text',
    name: 'tagsInput',
    message: `标签 (逗号分隔，常用: ${COMMON_TAGS.slice(0, 5).join(', ')}...)`,
  }, { onCancel });
  const tags = tagsInput ? tagsInput.split(/[,，]/).map(t => t.trim()).filter(Boolean) : [];

  const now = new Date();
  const dateStr = formatDate(now);
  const frontmatter = buildFrontmatter({ title: title.trim(), category, tags, date: dateStr });

  const dir = CATEGORIES[category].dir;
  const targetDir = subcategory
    ? path.join(POSTS_DIR, dir, subcategory)
    : path.join(POSTS_DIR, dir);

  fs.mkdirSync(targetDir, { recursive: true });
  const filePath = path.join(targetDir, `${title.trim()}.md`);

  if (fs.existsSync(filePath)) {
    console.error(`\x1b[31m文件已存在: ${filePath}\x1b[0m`);
    process.exit(1);
  }

  fs.writeFileSync(filePath, frontmatter + '\n');
  const relPath = path.relative(path.join(__dirname, '..'), filePath);
  console.log(`\x1b[32m✓ Created: ${relPath}\x1b[0m`);

  const { open } = await prompts({
    type: 'confirm',
    name: 'open',
    message: '打开文件?',
    initial: true,
  }, { onCancel });

  if (open) {
    const editor = process.env.EDITOR || 'code';
    try {
      execSync(`${editor} "${filePath}"`, { stdio: 'inherit' });
    } catch {}
  }
}

main().catch(console.error);
