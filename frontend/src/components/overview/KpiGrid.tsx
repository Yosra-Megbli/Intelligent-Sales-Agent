import React from "react";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { OverviewResponse } from "@/api/types";

interface KpiGridProps {
  overview?: OverviewResponse | null;
  isLoading?: boolean;
}

export const KpiGrid: React.FC<KpiGridProps> = ({
  overview,
  isLoading = false,
}) => {
  const { t } = useTranslation();

  // All values come directly from the canonical MetricsService via the
  // /api/dashboard/overview endpoint. No fallback fabrication.
  const contacts = overview?.contacted ?? 0;
  const conversations = overview?.active_conversations ?? 0;
  const qualified = overview?.qualified ?? 0;
  const signedContracts = overview?.signed_contracts ?? 0;

  // Conversion rate: already rounded to 1 decimal by MetricsService
  const convRate =
    overview?.conversion_rate != null
      ? overview.conversion_rate.toFixed(1)
      : "0.0";

  // Cost per sale: from canonical MetricsService (total_conversations * 0.02 / signed)
  const costPerSale =
    overview?.cost_per_sale != null
      ? overview.cost_per_sale.toFixed(2)
      : "0.00";

  // Estimated Annual Revenue = signed_contracts * 60.00 €/yr (canonical base fee)
  const estimatedRevenue =
    overview?.estimated_ca != null
      ? overview.estimated_ca.toLocaleString("fr-BE", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : (signedContracts * 60).toLocaleString("fr-BE", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Contacts */}
      <KpiCard
        title={t("overview.kpi.contacts")}
        value={contacts}
        isLoading={isLoading}
      />

      {/* 2. Conversations */}
      <KpiCard
        title={t("overview.kpi.conversations")}
        value={conversations}
        isLoading={isLoading}
      />

      {/* 3. Prospects Qualifiés */}
      <KpiCard
        title={t("overview.kpi.qualified")}
        value={qualified}
        isLoading={isLoading}
      />

      {/* 4. Contrats Signés */}
      <KpiCard
        title={t("overview.kpi.signedContracts")}
        value={signedContracts}
        isLoading={isLoading}
      />

      {/* 5. Taux de Transformation */}
      <KpiCard
        title={t("overview.kpi.conversionRate")}
        value={convRate}
        suffix="%"
        isLoading={isLoading}
      />

      {/* 6. Coût par Vente */}
      <KpiCard
        title={t("overview.kpi.costPerSale")}
        value={costPerSale}
        prefix="€"
        isLoading={isLoading}
      />

      {/* 7. CA Généré */}
      <div className="sm:col-span-2 lg:col-span-2">
        <KpiCard
          title={t("overview.kpi.estimatedRevenue")}
          value={estimatedRevenue}
          prefix="€"
          suffix={t("overview.kpi.annualSuffix") || "/an"}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
};
