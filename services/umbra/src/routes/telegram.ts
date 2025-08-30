import express from 'express';
import { TelegramClient, OpenRouterClient } from '@umbra/shared';
import { TelegramHandler } from '../telegram/telegram-handler';
import { Logger } from '@umbra/shared';

export function telegramRoutes(
  telegramClient: TelegramClient, 
  openRouterClient: OpenRouterClient
): express.Router {
  const router = express.Router();
  const logger = new Logger('TelegramRoutes');
  const telegramHandler = new TelegramHandler(telegramClient, openRouterClient);

  // Webhook endpoint for Telegram updates
  router.post('/', async (req, res) => {
    try {
      const update = req.body;
      
      logger.debug('Telegram update received', {
        updateId: update.update_id,
        hasMessage: !!update.message,
        hasCallback: !!update.callback_query
      });

      // Process update asynchronously to respond quickly to Telegram
      setImmediate(async () => {
        try {
          await telegramHandler.handleUpdate(update);
        } catch (error) {
          logger.error('Failed to process Telegram update', {
            updateId: update.update_id,
            error: error.message
          });
        }
      });

      // Respond immediately to Telegram
      res.status(200).json({ ok: true });

    } catch (error) {
      logger.error('Telegram webhook error', {
        error: error.message,
        body: req.body
      });

      res.status(500).json({ 
        ok: false, 
        error: 'Internal server error' 
      });
    }
  });

  // Manual message sending endpoint (for testing)
  if (process.env.NODE_ENV === 'development') {
    router.post('/send', async (req, res) => {
      try {
        const { chatId, message, lang = 'EN' } = req.body;
        
        if (!chatId || !message) {
          return res.status(400).json({
            error: 'chatId and message are required'
          });
        }

        await telegramClient.sendLocalizedMessage(chatId, 'custom', { message }, lang);
        
        res.json({ success: true });
      } catch (error) {
        logger.error('Manual message send failed', { error: error.message });
        res.status(500).json({ error: error.message });
      }
    });
  }

  return router;
}