/**
 * Puppeteer 截图脚本。
 * 用法: node preview.js <url> <output_path> [section_selector]
 */

const puppeteer = require("puppeteer");

async function main() {
  const [url, outputPath, sectionSelector] = process.argv.slice(2);

  if (!url || !outputPath) {
    console.error("Usage: node preview.js <url> <output_path> [section_selector]");
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 800 });
    await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });

    // 等待内容渲染，避免截到 NexT motion 动画中正文仍为 hidden 的中间帧
    try {
      await page.waitForSelector(".post-body", { timeout: 10000 });
      await page.waitForFunction(
        () => {
          const postBody = document.querySelector(".post-body");
          if (!postBody) {
            return false;
          }

          const postBodyStyle = window.getComputedStyle(postBody);
          const postBlock = document.querySelector(".post-block");
          const postBlockStyle = postBlock
            ? window.getComputedStyle(postBlock)
            : null;

          const postBodyVisible =
            postBodyStyle.visibility !== "hidden" &&
            postBodyStyle.display !== "none" &&
            Number.parseFloat(postBodyStyle.opacity || "1") > 0.9;

          const postBlockVisible =
            !postBlockStyle ||
            (postBlockStyle.visibility !== "hidden" &&
              Number.parseFloat(postBlockStyle.opacity || "1") > 0.9);

          return postBodyVisible && postBlockVisible;
        },
        { timeout: 10000 }
      );
    } catch {
      // 可能是 404 或页面结构不同，继续截图
    }

    if (sectionSelector) {
      try {
        await page.waitForFunction(
          (selector) => {
            const element = document.querySelector(selector);
            if (!element) {
              return false;
            }

            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return (
              style.visibility !== "hidden" &&
              style.display !== "none" &&
              rect.width > 0 &&
              rect.height > 0
            );
          },
          { timeout: 5000 },
          sectionSelector
        );
      } catch {
        // 选择器不存在或尚未可见时，沿用后面的整页回退逻辑
      }
    }

    if (sectionSelector) {
      const element = await page.$(sectionSelector);
      if (element) {
        await element.screenshot({ path: outputPath });
      } else {
        await page.screenshot({ path: outputPath, fullPage: true });
      }
    } else {
      await page.screenshot({ path: outputPath, fullPage: true });
    }

    console.log(outputPath);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
