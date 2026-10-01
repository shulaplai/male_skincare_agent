import { expect, test } from '@playwright/test'
import { CONVERSATION_ID, installFixtures } from './fixtures'

/**
 * Sheet／Toast 取代 `window.prompt`／`window.confirm`／`window.alert`（Phase 2a）。
 *
 * 為咩要真係測：iOS Safari 連續彈幾個 `prompt()` 會**靜靜封鎖**後面嗰啲，
 * IG／FB in-app browser 直情 disable —— 即係舊寫法喺真手機上會「撳咗冇反應」。
 * 所以呢度唔止測「有 Sheet」，仲要**證明 native dialog 冇被呼叫**。
 */
async function spyNativeDialogs(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>
    w.__dialogs = []
    for (const name of ['prompt', 'confirm', 'alert']) {
      w[name] = (...args: unknown[]) => {
        ;(w.__dialogs as unknown[]).push([name, String(args[0] ?? '')])
        return name === 'confirm' ? true : ''
      }
    }
  })
}

test('改名：出 Sheet（唔係 window.prompt），儲存後出 toast', async ({ page }) => {
  await spyNativeDialogs(page)
  await installFixtures(page)
  let renamed: string | null = null
  await page.route(`**/api/conversations/${CONVERSATION_ID}`, (r) => {
    if (r.request().method() === 'PUT') {
      renamed = JSON.parse(r.request().postData() ?? '{}').body_part
      return r.fulfill({ json: { id: CONVERSATION_ID, body_part: renamed, icon: '🧔', cloud_analysis: true } })
    }
    return r.fallback()
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=settings')
  await page.waitForLoadState('networkidle')

  await page.getByRole('button', { name: '改名' }).first().click()
  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  await expect(sheet).toHaveAttribute('aria-modal', 'true')

  // Escape 要關得到（鍵盤用戶）
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()

  await page.getByRole('button', { name: '改名' }).first().click()
  const field = page.getByRole('dialog').getByRole('textbox')
  await field.fill('背部')
  await page.getByRole('dialog').getByRole('button', { name: '儲存' }).click()
  await expect(page.locator('.toast')).toBeVisible()
  expect(renamed).toBe('背部')

  const dialogs = await page.evaluate(() => (window as unknown as { __dialogs: unknown[] }).__dialogs)
  expect(dialogs, `唔應該再彈 native dialog：${JSON.stringify(dialogs)}`).toEqual([])
})

test('刪除部位：出 Sheet 確認，取消唔會叫 API', async ({ page }) => {
  await spyNativeDialogs(page)
  await installFixtures(page)
  let deleted = false
  await page.route(`**/api/conversations/${CONVERSATION_ID}`, (r) => {
    if (r.request().method() === 'DELETE') {
      deleted = true
      return r.fulfill({ json: { status: 'deleted' } })
    }
    return r.fallback()
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=settings')
  await page.waitForLoadState('networkidle')

  await page.getByRole('button', { name: '刪除' }).first().click()
  const sheet = page.getByRole('dialog')
  await expect(sheet).toContainText('永久刪除')
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
  await expect(sheet).toBeHidden()
  expect(deleted, '取消之後唔應該刪').toBe(false)

  await page.getByRole('button', { name: '刪除' }).first().click()
  await page.getByRole('dialog').getByRole('button', { name: '確定刪除' }).click()
  await expect.poll(() => deleted).toBe(true)

  const dialogs = await page.evaluate(() => (window as unknown as { __dialogs: unknown[] }).__dialogs)
  expect(dialogs).toEqual([])
})

test('Sheet 開嘅時候 focus 入去，關嘅時候還返（鍵盤用戶唔會迷失）', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=settings')
  await page.waitForLoadState('networkidle')

  const trigger = page.getByRole('button', { name: '改名' }).first()
  await trigger.click()
  await expect(page.getByRole('dialog').getByRole('textbox')).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('相片：撳「顯示」解除模糊，再撳開全螢幕，Escape 關返', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  const reveal = page.locator('.photo .reveal').first()
  await expect(reveal).toBeVisible()
  await reveal.click()
  await expect(page.locator('.photo.blurred')).toHaveCount(0)

  await page.locator('.photo-open').first().click()
  const box = page.getByRole('dialog', { name: '皮膚相（全螢幕）' })
  await expect(box).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(box).toBeHidden()
})

test('暗色模式：html[data-theme] 跟 localStorage，文字仍然夠對比', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('skc-theme', 'dark'))
  await installFixtures(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  // dark token 必須係淺色字（--text #f4e7ec）；如果邊度漏咗 token，呢度會捉到
  const color = await page.locator('.bubble').first().evaluate((el) => getComputedStyle(el).color)
  expect(color).toBe('rgb(244, 231, 236)')
})
