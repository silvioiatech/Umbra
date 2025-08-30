import { OpenRouterClient } from '@umbra/shared';
import { Envelope, FinancePayload, ModuleResult } from '@umbra/shared';
import { Logger } from '@umbra/shared';

export class FinancialCategorizer {
  private logger: Logger;
  private openRouterClient: OpenRouterClient;

  private categories = [
    'Office Supplies', 'Travel', 'Meals & Entertainment', 'Software', 'Marketing',
    'Professional Services', 'Utilities', 'Rent', 'Insurance', 'Equipment',
    'Training', 'Subscriptions', 'Banking Fees', 'Taxes', 'Other'
  ];

  constructor(openRouterClient: OpenRouterClient) {
    this.logger = new Logger('FinancialCategorizer');
    this.openRouterClient = openRouterClient;
  }

  async categorizeTransaction(envelope: Envelope<FinancePayload>): Promise<ModuleResult<any>> {
    const { reqId, userId, payload } = envelope;
    const startTime = Date.now();

    try {
      const transactionData = payload.transactionData || payload;
      
      const category = await this.classifyExpense(transactionData);
      
      const durationMs = Date.now() - startTime;

      return {
        reqId,
        status: 'success',
        data: {
          originalCategory: transactionData.category,
          suggestedCategory: category.category,
          confidence: category.confidence,
          reasoning: category.reasoning
        },
        audit: {
          module: 'finance-categorizer',
          durationMs
        }
      };

    } catch (error) {
      this.logger.error('Categorization failed', { reqId, error: error.message });
      
      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CATEGORIZATION_ERROR',
          message: 'Failed to categorize transaction',
          retryable: true
        }
      };
    }
  }

  private async classifyExpense(data: any): Promise<any> {
    const prompt = `
Categorize this financial transaction into one of these categories:
${this.categories.join(', ')}

Transaction details:
- Vendor: ${data.vendor || 'Unknown'}
- Description: ${data.description || 'No description'}
- Amount: ${data.amount || 'Unknown'}

Return JSON:
{
  "category": "exact category name from list",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}
`;

    try {
      const result = await this.openRouterClient.generateJSON(prompt);
      return {
        category: result.category || 'Other',
        confidence: result.confidence || 0.5,
        reasoning: result.reasoning || 'Automatic categorization'
      };
    } catch (error) {
      return {
        category: 'Other',
        confidence: 0.1,
        reasoning: 'Failed to categorize automatically'
      };
    }
  }
}