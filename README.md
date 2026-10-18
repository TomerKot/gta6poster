# GTA 6 → Telegram (автоканал, бюджет $0)

Бот раз на ~30 хвилин збирає новини про GTA 6 з відкритих RSS-стрічок, фільтрує,
прибирає дублі й публікує в Telegram-канал. Працює повністю в **GitHub Actions** —
сервер, VPS і платні API не потрібні.

## Як це працює

```
GitHub Actions (cron) → RSS-джерела → фільтри (тема / блок-лист / чутки)
→ дедуплікація (URL + заголовок) → Telegram Bot API → state/seen.json (коміт)
```

Постимо **заголовок + короткий уривок + посилання з атрибуцією**, не копіюємо статті цілком.

## Запуск за 10 хвилин

1. **Бот.** У Telegram → `@BotFather` → `/newbot` → збережи токен.
2. **Канал.** Створи публічний канал (або приватний), додай бота в **адміністратори** з єдиним
   правом **«Публікація повідомлень»** — решту прав вимкни.
3. **Репозиторій.** Створи репозиторій на GitHub (рекомендовано **public**: Actions безкоштовні
   без ліміту хвилин; у private — 2000 хв/міс, нам вистачає з запасом) і залий туди ці файли.
4. **Секрети.** Settings → Secrets and variables → Actions → *New repository secret*:
   - `TELEGRAM_BOT_TOKEN` — токен від BotFather
   - `TELEGRAM_CHAT_ID` — `@username_каналу` (для приватного — числовий `-100…`)
5. **Захист репозиторію** (Settings → Code security): увімкни *Secret scanning* + *Push protection*,
   *Dependabot alerts*. У Settings → Actions → General постав *Workflow permissions: Read repository
   contents* (workflow сам просить `contents: write` лише для state-файлу).
6. **Перевірка.** Actions → *post-news* → *Run workflow* з `dry_run = true` → дивись лог:
   які джерела відповіли, що було б опубліковано. Потім запусти з `dry_run = false`.
   **Перший реальний запуск нічого не постить** — він лише запам'ятовує поточні новини, щоб
   не засипати канал старим. Далі йдуть тільки свіжі.

## Налаштування

Усе в `config/config.toml`: джерела, ключові слова, блок-лист, ліміти. Додати джерело —
додай блок `[[sources]]` з RSS-URL. Локально:

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m gta6bot.main --dry-run
python -m unittest discover -s tests
```

## Що свідомо не підключено і чому

Див. `docs/ANALYSIS.md` (X/Twitter, Reddit, скрапінг, Nitter) та `SECURITY.md` (модель загроз).

## Відомі обмеження

- GitHub-cron не гарантує точності (затримки 5–20 хв — норма).
- Якщо в репозиторії 60 днів нема активності, GitHub вимикає cron. Бот сам комітить
  «heartbeat» раз на місяць, тож цього не станеться.
- Фіди можуть змінити URL — дивись попередження `source '…' failed` у логах.
