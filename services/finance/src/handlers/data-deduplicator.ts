import { Envelope, FinancePayload, ModuleResult } from '@umbra/shared';
import Logger from '@umbra/shared/src/utils/logger';
import { CryptoUtils } from '@umbra/shared';

interface TransactionRecord {
  id: string;
  vendor?: string;
  amount?: number;
  date?: string;
  description?: string;
  hash?: string;
}

export class DataDeduplicator {
  private logger: Logger;
  private records: Map<string, TransactionRecord[]> = new Map();

  constructor() {
    this.logger = new Logger('DataDeduplicator');
  }

  async deduplicateRecords(envelope: Envelope<FinancePayload>): Promise<ModuleResult<any>> {
    const { reqId, userId, payload } = envelope;
    const startTime = Date.now();

    try {
      const records = payload.records || [];
      const duplicates = await this.findDuplicates(records, userId);
      
      const durationMs = Date.now() - startTime;

      return {
        reqId,
        status: 'success',
        data: {
          totalRecords: records.length,
          duplicatesFound: duplicates.length,
          duplicates: duplicates,
          uniqueRecords: records.filter(r => !duplicates.find(d => d.id === r.id))
        },
        audit: {
          module: 'finance-deduplicator',
          durationMs
        }
      };

    } catch (error) {
      this.logger.error('Deduplication failed', { reqId, error: error.message });
      
      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'DEDUPLICATION_ERROR',
          message: 'Failed to deduplicate records',
          retryable: true
        }
      };
    }
  }

  private async findDuplicates(records: any[], userId: string): Promise<any[]> {
    const duplicates: any[] = [];
    const seen = new Set<string>();

    for (const record of records) {
      const hash = this.generateRecordHash(record);
      
      if (seen.has(hash)) {
        duplicates.push({
          ...record,
          duplicateHash: hash,
          reason: 'Exact match'
        });
      } else {
        seen.add(hash);
      }
    }

    // Store records for future deduplication
    this.records.set(userId, records);

    return duplicates;
  }

  private generateRecordHash(record: any): string {
    const key = `${record.vendor || ''}-${record.amount || ''}-${record.date || ''}`
      .toLowerCase()
      .replace(/\s+/g, '');
    
    return CryptoUtils.hashForLogging(key);
  }
}