"""Financial report generation."""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from umbra_shared import (
    OpenRouterClient,
    UmbraLogger,
    StorageClient,
    Envelope,
    FinancePayload,
    ModuleResult,
    FinanceResult,
)


class ReportGenerator:
    """Generate financial reports and summaries."""
    
    def __init__(self, openrouter_client: OpenRouterClient, storage_client: Optional[StorageClient] = None):
        self.logger = UmbraLogger("ReportGenerator")
        self.openrouter_client = openrouter_client
        self.storage_client = storage_client
        
        # Report templates
        self.report_templates = {
            "budget": self._generate_budget_report,
            "vat": self._generate_vat_report,
            "tax": self._generate_tax_report,
            "expense": self._generate_expense_report,
            "summary": self._generate_summary_report
        }
    
    async def generate_report(
        self,
        envelope: Envelope[FinancePayload]
    ) -> ModuleResult[FinanceResult]:
        """Generate financial report based on request."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        report_type = envelope.payload.report_type or "summary"
        
        try:
            self.logger.info("Starting report generation",
                           req_id=req_id,
                           report_type=report_type)
            
            # Get date range
            date_range = envelope.payload.date_range
            if not date_range:
                # Default to current month
                now = datetime.now()
                start_date = now.replace(day=1).strftime("%Y-%m-%d")
                end_date = now.strftime("%Y-%m-%d")
                date_range = {"start": start_date, "end": end_date}
            
            # Generate report based on type
            if report_type in self.report_templates:
                report_data = await self.report_templates[report_type](
                    envelope.user_id,
                    date_range,
                    envelope.lang
                )
            else:
                return ModuleResult(
                    req_id=req_id,
                    status="error",
                    error={
                        "type": "functional",
                        "code": "INVALID_REPORT_TYPE",
                        "message": f"Invalid report type: {report_type}",
                        "retryable": False
                    }
                )
            
            # Store report if storage is available
            report_url = None
            if self.storage_client and report_data:
                report_url = await self._store_report(
                    req_id,
                    envelope.user_id,
                    report_type,
                    report_data
                )
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result_data = FinanceResult(
                report_data=report_data,
                document_url=report_url,
                confidence=1.0,
                needs_review=False
            )
            
            self.logger.info("Report generation completed",
                           req_id=req_id,
                           report_type=report_type,
                           url=report_url)
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data=result_data,
                audit={
                    "module": "finance-reports",
                    "duration_ms": duration_ms,
                    "report_type": report_type,
                    "date_range": date_range
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Report generation failed",
                            req_id=req_id,
                            report_type=report_type,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "REPORT_GENERATION_ERROR",
                    "message": f"Report generation failed: {str(e)}",
                    "retryable": True
                },
                audit={
                    "module": "finance-reports",
                    "duration_ms": duration_ms
                }
            )
    
    async def _generate_budget_report(
        self,
        user_id: str,
        date_range: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Generate budget analysis report."""
        # In a real implementation, this would fetch actual transaction data
        # For now, we'll create a mock report structure
        
        mock_expenses = [
            {"category": "office_supplies", "amount": 245.50, "currency": "EUR"},
            {"category": "software", "amount": 99.99, "currency": "EUR"},
            {"category": "travel", "amount": 450.00, "currency": "EUR"},
            {"category": "meals", "amount": 180.25, "currency": "EUR"},
        ]
        
        total_expenses = sum(exp["amount"] for exp in mock_expenses)
        
        report = {
            "report_type": "budget",
            "period": date_range,
            "currency": "EUR",
            "total_expenses": total_expenses,
            "expense_breakdown": mock_expenses,
            "budget_analysis": {
                "total_budget": 2000.00,  # Mock budget
                "spent": total_expenses,
                "remaining": 2000.00 - total_expenses,
                "usage_percentage": (total_expenses / 2000.00) * 100
            },
            "recommendations": await self._get_budget_recommendations(mock_expenses, language)
        }
        
        return report
    
    async def _generate_vat_report(
        self,
        user_id: str,
        date_range: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Generate VAT report."""
        # Mock VAT data
        vat_transactions = [
            {
                "vendor": "Office Supplies Ltd",
                "net_amount": 200.00,
                "vat_amount": 40.00,
                "total_amount": 240.00,
                "vat_rate": 0.20,
                "date": "2024-01-15"
            },
            {
                "vendor": "Software Inc",
                "net_amount": 83.33,
                "vat_amount": 16.67,
                "total_amount": 100.00,
                "vat_rate": 0.20,
                "date": "2024-01-20"
            }
        ]
        
        total_net = sum(t["net_amount"] for t in vat_transactions)
        total_vat = sum(t["vat_amount"] for t in vat_transactions)
        total_gross = sum(t["total_amount"] for t in vat_transactions)
        
        report = {
            "report_type": "vat",
            "period": date_range,
            "currency": "EUR",
            "summary": {
                "total_net_amount": total_net,
                "total_vat_amount": total_vat,
                "total_gross_amount": total_gross,
                "transaction_count": len(vat_transactions)
            },
            "transactions": vat_transactions,
            "vat_breakdown": {
                "20%": {"count": len(vat_transactions), "vat_amount": total_vat}
            }
        }
        
        return report
    
    async def _generate_tax_report(
        self,
        user_id: str,
        date_range: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Generate tax report."""
        # Mock tax data
        deductible_expenses = [
            {"category": "office_supplies", "amount": 245.50, "deductible": True},
            {"category": "software", "amount": 99.99, "deductible": True},
            {"category": "travel", "amount": 450.00, "deductible": True},
            {"category": "meals", "amount": 180.25, "deductible": False},  # Only 50% typically
        ]
        
        total_deductible = sum(
            exp["amount"] if exp["deductible"] else exp["amount"] * 0.5 
            for exp in deductible_expenses
        )
        
        report = {
            "report_type": "tax",
            "period": date_range,
            "currency": "EUR",
            "deductible_expenses": {
                "total_amount": total_deductible,
                "breakdown": deductible_expenses
            },
            "tax_savings_estimate": total_deductible * 0.25,  # Assuming 25% tax rate
            "recommendations": await self._get_tax_recommendations(deductible_expenses, language)
        }
        
        return report
    
    async def _generate_expense_report(
        self,
        user_id: str,
        date_range: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Generate detailed expense report."""
        # Mock expense data
        expenses = [
            {
                "date": "2024-01-15",
                "vendor": "Office Supplies Ltd",
                "category": "office_supplies",
                "amount": 245.50,
                "currency": "EUR",
                "description": "Stationery and office materials"
            },
            {
                "date": "2024-01-20",
                "vendor": "Software Inc",
                "category": "software",
                "amount": 99.99,
                "currency": "EUR",
                "description": "Monthly subscription"
            }
        ]
        
        # Group by category
        category_totals = {}
        for expense in expenses:
            category = expense["category"]
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += expense["amount"]
        
        report = {
            "report_type": "expense",
            "period": date_range,
            "currency": "EUR",
            "total_expenses": sum(exp["amount"] for exp in expenses),
            "expense_count": len(expenses),
            "category_breakdown": category_totals,
            "detailed_expenses": expenses,
            "insights": await self._get_expense_insights(expenses, language)
        }
        
        return report
    
    async def _generate_summary_report(
        self,
        user_id: str,
        date_range: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """Generate summary report with key metrics."""
        # Combine data from other reports
        budget_data = await self._generate_budget_report(user_id, date_range, language)
        vat_data = await self._generate_vat_report(user_id, date_range, language)
        
        report = {
            "report_type": "summary",
            "period": date_range,
            "currency": "EUR",
            "key_metrics": {
                "total_expenses": budget_data["total_expenses"],
                "total_vat": vat_data["summary"]["total_vat_amount"],
                "expense_categories": len(budget_data["expense_breakdown"]),
                "transaction_count": vat_data["summary"]["transaction_count"]
            },
            "budget_status": budget_data["budget_analysis"],
            "top_categories": sorted(
                budget_data["expense_breakdown"],
                key=lambda x: x["amount"],
                reverse=True
            )[:3],
            "alerts": await self._generate_alerts(budget_data, vat_data, language)
        }
        
        return report
    
    async def _get_budget_recommendations(
        self,
        expenses: List[Dict[str, Any]],
        language: str
    ) -> List[str]:
        """Generate budget recommendations using AI."""
        try:
            expense_summary = json.dumps(expenses, indent=2)
            
            prompts = {
                "EN": f"Based on these expenses, provide 3 budget optimization recommendations:\n{expense_summary}",
                "FR": f"Basé sur ces dépenses, fournissez 3 recommandations d'optimisation budgétaire:\n{expense_summary}",
                "PT": f"Com base nessas despesas, forneça 3 recomendações de otimização orçamentária:\n{expense_summary}"
            }
            
            prompt = prompts.get(language, prompts["EN"])
            
            messages = [
                {"role": "system", "content": "You are a financial advisor. Provide practical, actionable budget recommendations."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.openrouter_client.chat_completion(
                model="openai/gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            
            recommendations = response.choices[0].message.content.strip().split('\n')
            return [rec.strip() for rec in recommendations if rec.strip()]
            
        except Exception as e:
            self.logger.warning("AI recommendations failed", error=str(e))
            
            # Fallback recommendations
            fallback = {
                "EN": [
                    "Review recurring software subscriptions for optimization",
                    "Set monthly budget limits for each expense category",
                    "Consider bulk purchasing for office supplies"
                ],
                "FR": [
                    "Examiner les abonnements logiciels récurrents pour optimisation",
                    "Définir des limites budgétaires mensuelles par catégorie",
                    "Considérer les achats en gros pour les fournitures"
                ],
                "PT": [
                    "Revisar assinaturas de software recorrentes para otimização",
                    "Definir limites orçamentários mensais por categoria",
                    "Considerar compras em quantidade para suprimentos"
                ]
            }
            
            return fallback.get(language, fallback["EN"])
    
    async def _get_tax_recommendations(
        self,
        expenses: List[Dict[str, Any]],
        language: str
    ) -> List[str]:
        """Generate tax optimization recommendations."""
        recommendations = {
            "EN": [
                "Keep detailed receipts for all business expenses",
                "Separate business and personal expenses clearly",
                "Consider quarterly tax payments to avoid penalties"
            ],
            "FR": [
                "Conserver les reçus détaillés pour toutes les dépenses professionnelles",
                "Séparer clairement les dépenses professionnelles et personnelles",
                "Considérer les paiements d'impôts trimestriels"
            ],
            "PT": [
                "Manter recibos detalhados para todas as despesas comerciais",
                "Separar claramente despesas comerciais e pessoais",
                "Considerar pagamentos de impostos trimestrais"
            ]
        }
        
        return recommendations.get(language, recommendations["EN"])
    
    async def _get_expense_insights(
        self,
        expenses: List[Dict[str, Any]],
        language: str
    ) -> List[str]:
        """Generate expense insights."""
        insights = {
            "EN": [
                f"Average expense amount: €{sum(e['amount'] for e in expenses) / len(expenses):.2f}",
                f"Most frequent category: {max(set(e['category'] for e in expenses), key=lambda x: sum(1 for e in expenses if e['category'] == x))}",
                f"Total transactions: {len(expenses)}"
            ],
            "FR": [
                f"Montant moyen des dépenses: €{sum(e['amount'] for e in expenses) / len(expenses):.2f}",
                f"Catégorie la plus fréquente: {max(set(e['category'] for e in expenses), key=lambda x: sum(1 for e in expenses if e['category'] == x))}",
                f"Total des transactions: {len(expenses)}"
            ],
            "PT": [
                f"Valor médio das despesas: €{sum(e['amount'] for e in expenses) / len(expenses):.2f}",
                f"Categoria mais frequente: {max(set(e['category'] for e in expenses), key=lambda x: sum(1 for e in expenses if e['category'] == x))}",
                f"Total de transações: {len(expenses)}"
            ]
        }
        
        return insights.get(language, insights["EN"])
    
    async def _generate_alerts(
        self,
        budget_data: Dict[str, Any],
        vat_data: Dict[str, Any],
        language: str
    ) -> List[str]:
        """Generate financial alerts and warnings."""
        alerts = []
        
        # Budget alerts
        usage_pct = budget_data["budget_analysis"]["usage_percentage"]
        if usage_pct > 90:
            alert_texts = {
                "EN": "⚠️ Budget usage is over 90%",
                "FR": "⚠️ Utilisation du budget supérieure à 90%",
                "PT": "⚠️ Uso do orçamento acima de 90%"
            }
            alerts.append(alert_texts.get(language, alert_texts["EN"]))
        
        # VAT alerts
        if vat_data["summary"]["total_vat_amount"] > 500:
            alert_texts = {
                "EN": "💰 High VAT amount - consider quarterly filing",
                "FR": "💰 Montant de TVA élevé - considérez la déclaration trimestrielle",
                "PT": "💰 Valor alto de IVA - considere declaração trimestral"
            }
            alerts.append(alert_texts.get(language, alert_texts["EN"]))
        
        return alerts
    
    async def _store_report(
        self,
        req_id: str,
        user_id: str,
        report_type: str,
        report_data: Dict[str, Any]
    ) -> Optional[str]:
        """Store report in cloud storage."""
        try:
            if not self.storage_client:
                return None
            
            # Generate report as JSON
            report_json = json.dumps(report_data, indent=2, default=str)
            report_bytes = report_json.encode('utf-8')
            
            # Generate storage key
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"reports/{user_id}/{report_type}_{timestamp}_{req_id}.json"
            
            # Upload to storage
            url = await self.storage_client.upload_file(
                file_data=report_bytes,
                key=key,
                content_type="application/json",
                metadata={
                    "user_id": user_id,
                    "report_type": report_type,
                    "req_id": req_id
                }
            )
            
            self.logger.info("Report stored successfully", key=key, url=url)
            return url
            
        except Exception as e:
            self.logger.error("Failed to store report", error=str(e))
            return None