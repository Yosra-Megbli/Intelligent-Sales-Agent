/**
 * Export Engine for Sophie AI (Ecofix Belgique)
 * Generates ultra-legible CSV (with UTF-8 BOM, ';' delimiter, reordered columns, text-guarded dates)
 * and SpreadsheetML Excel (.xls) files with full styling: custom column widths, Ecofix brand colors,
 * zebra alternating rows, status badges, and zero '#####' truncation.
 */

import { LeadSummary, OverviewResponse, StatsSummaryResponse, ActivityFeedEntryResponse } from "@/api/types";

// Region mapping
export const REGION_LABELS: Record<string, string> = {
  Flandre: "Flandre (Fluvius)",
  Wallonie: "Wallonie (ORES / RESA)",
  Bruxelles: "Bruxelles (Hors zone)",
  BE: "Belgique (National)",
};

export const STATUS_LABELS: Record<string, string> = {
  NEW: "Nouveau",
  CONTACTED: "Engagé / Contacté",
  QUALIFIED_FLEXY: "Qualifié Flexy",
  QUALIFIED_MOTION: "Qualifié Motion",
  FIXED_SEEKER: "Cherche Fixe (Refusé)",
  OPT_OUT: "Désinscrit (RGPD)",
  LOST: "Perdu / Non intéressé",
  HUMAN_HANDOFF: "Relais Conseiller Humain",
  SIGNED: "Contrat Signé",
};

// OWASP CSV formula injection guard
const CSV_FORMULA_PREFIX = /^[=+\-@\t\r]/;
const sanitizeCsv = (val: string | number | null | undefined): string => {
  if (val === null || val === undefined) return "";
  const str = String(val).trim();
  if (!str) return "";
  return CSV_FORMULA_PREFIX.test(str) ? `'${str}` : str;
};

// Guard string for Excel so dates/numbers are never collapsed to "#####"
const excelText = (val: string | number | null | undefined): string => {
  if (val === null || val === undefined) return "";
  const s = String(val).trim();
  if (!s) return "";
  return `="${s.replace(/"/g, '""')}"`;
};

// Clean formatted date as DD/MM/YYYY HH:mm
export const formatDisplayDate = (iso: string | null | undefined): string => {
  if (!iso) return "N/A";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${day}/${month}/${year} ${hours}:${minutes}`;
  } catch {
    return String(iso);
  }
};

const triggerDownload = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

// ==========================================
// 1. LEADS EXPORT (CSV & EXCEL STYLISÉ)
// ==========================================

export const exportLeadsToCsv = (leads: LeadSummary[]) => {
  if (!leads.length) return;
  const now = new Date();
  const dateStamp = now.toISOString().slice(0, 10);
  const timeStamp = formatDisplayDate(now.toISOString());

  const lines: string[] = [
    `"=== ECOFIX BELGIQUE • RAPPORT PROSPECTS CRM (SOPHIE AI) ===";;;;;;;;;;`,
    `"Date d'exportation";"${timeStamp}";;;;;;;;`,
    `"Total des prospects";"${leads.length}";;;;;;;;`,
    `"Environnement";"Production Render Live";;;;;;;;`,
    `;;;;;;;;;;`,
    [
      "Nom",
      "Prénom",
      "Téléphone",
      "Email",
      "Statut Commercial",
      "Région",
      "Gestionnaire de réseau (GRD)",
      "Fournisseur Actuel",
      "Code EAN (18 chiffres)",
      "Date de Création",
      "ID Technique",
    ]
      .map((h) => `"${h}"`)
      .join(";"),
  ];

  leads.forEach((lead) => {
    const isOpt = lead.status === "OPT_OUT";
    const region = lead.region ? REGION_LABELS[lead.region] || lead.region : "Non renseigné";
    const grd =
      lead.region === "Flandre"
        ? "Fluvius"
        : lead.region === "Wallonie"
        ? "ORES / RESA"
        : lead.region === "Bruxelles"
        ? "Sibelga (Non desservi)"
        : "Standard";

    const statusLabel = STATUS_LABELS[lead.status] || lead.status;

    const row = [
      isOpt ? "RGPD_PURGÉ" : sanitizeCsv(lead.last_name || "Non renseigné"),
      isOpt ? "RGPD_PURGÉ" : sanitizeCsv(lead.first_name || "Non renseigné"),
      isOpt ? "-" : excelText(lead.phone || "-"),
      isOpt ? "-" : sanitizeCsv(lead.email || "-"),
      sanitizeCsv(statusLabel),
      sanitizeCsv(region),
      sanitizeCsv(grd),
      sanitizeCsv(lead.current_supplier || "Non renseigné"),
      isOpt ? "-" : excelText(lead.ean || "-"),
      excelText(formatDisplayDate(lead.created_at)),
      excelText(lead.id),
    ];

    lines.push(row.map((val) => (val.startsWith("=") ? val : `"${val.replace(/"/g, '""')}"`)).join(";"));
  });

  const csvContent = lines.join("\r\n");
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, `prospects-ecofix-${dateStamp}.csv`);
};

export const exportLeadsToExcel = (leads: LeadSummary[]) => {
  if (!leads.length) return;
  const now = new Date();
  const dateStamp = now.toISOString().slice(0, 10);
  const timeStamp = formatDisplayDate(now.toISOString());

  const xmlStyles = `
    <Style ss:ID="Default" ss:Name="Normal">
      <Alignment ss:Vertical="Center"/>
      <Font ss:FontName="Segoe UI" ss:Size="10" ss:Color="#0F172A"/>
    </Style>
    <Style ss:ID="BannerTitle">
      <Font ss:FontName="Segoe UI" ss:Size="14" ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center" ss:Indent="1"/>
    </Style>
    <Style ss:ID="BannerMeta">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Color="#94A3B8"/>
      <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center" ss:Indent="1"/>
    </Style>
    <Style ss:ID="TableHeader">
      <Font ss:FontName="Segoe UI" ss:Size="10" ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#0D9488" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="2" ss:Color="#0F766E"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#14B8A6"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#14B8A6"/>
      </Borders>
    </Style>
    <Style ss:ID="RowEven">
      <Interior ss:Color="#FFFFFF" ss:Pattern="Solid"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#F1F5F9"/>
      </Borders>
      <Alignment ss:Vertical="Center"/>
    </Style>
    <Style ss:ID="RowOdd">
      <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#F1F5F9"/>
      </Borders>
      <Alignment ss:Vertical="Center"/>
    </Style>
    <Style ss:ID="StatusQualified">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Bold="1" ss:Color="#166534"/>
      <Interior ss:Color="#DCFCE7" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#BBF7D0"/>
      </Borders>
    </Style>
    <Style ss:ID="StatusContacted">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Bold="1" ss:Color="#0369A1"/>
      <Interior ss:Color="#E0F2FE" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#BAE6FD"/>
      </Borders>
    </Style>
    <Style ss:ID="StatusNew">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Bold="1" ss:Color="#4338CA"/>
      <Interior ss:Color="#EEF2FF" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E0E7FF"/>
      </Borders>
    </Style>
    <Style ss:ID="StatusOptOut">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Bold="1" ss:Color="#991B1B"/>
      <Interior ss:Color="#FEE2E2" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#FECACA"/>
      </Borders>
    </Style>
    <Style ss:ID="StatusHandoff">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Bold="1" ss:Color="#92400E"/>
      <Interior ss:Color="#FEF3C7" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#FDE68A"/>
      </Borders>
    </Style>
    <Style ss:ID="DateCell">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Color="#475569"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
    </Style>
    <Style ss:ID="CodeCell">
      <Font ss:FontName="Consolas" ss:Size="8" ss:Color="#64748B"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
    </Style>
  `;

  let rowsXml = "";
  leads.forEach((lead, idx) => {
    const isOpt = lead.status === "OPT_OUT";
    const baseStyle = idx % 2 === 0 ? "RowEven" : "RowOdd";

    let statusStyle = baseStyle;
    if (lead.status.startsWith("QUALIFIED")) statusStyle = "StatusQualified";
    else if (lead.status === "CONTACTED") statusStyle = "StatusContacted";
    else if (lead.status === "NEW") statusStyle = "StatusNew";
    else if (lead.status === "OPT_OUT") statusStyle = "StatusOptOut";
    else if (lead.status === "HUMAN_HANDOFF") statusStyle = "StatusHandoff";

    const region = lead.region ? REGION_LABELS[lead.region] || lead.region : "Non renseigné";
    const grd =
      lead.region === "Flandre"
        ? "Fluvius"
        : lead.region === "Wallonie"
        ? "ORES / RESA"
        : lead.region === "Bruxelles"
        ? "Sibelga (Non desservi)"
        : "Standard";

    rowsXml += `
      <Row ss:Height="22">
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(isOpt ? "RGPD_PURGÉ" : lead.last_name || "Non renseigné")}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(isOpt ? "RGPD_PURGÉ" : lead.first_name || "Non renseigné")}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(isOpt ? "-" : lead.phone || "-")}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(isOpt ? "-" : lead.email || "-")}</Data></Cell>
        <Cell ss:StyleID="${statusStyle}"><Data ss:Type="String">${escapeXml(STATUS_LABELS[lead.status] || lead.status)}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(region)}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(grd)}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(lead.current_supplier || "Non renseigné")}</Data></Cell>
        <Cell ss:StyleID="${baseStyle}"><Data ss:Type="String">${escapeXml(isOpt ? "-" : lead.ean || "-")}</Data></Cell>
        <Cell ss:StyleID="DateCell"><Data ss:Type="String">${escapeXml(formatDisplayDate(lead.created_at))}</Data></Cell>
        <Cell ss:StyleID="CodeCell"><Data ss:Type="String">${escapeXml(lead.id)}</Data></Cell>
      </Row>
    `;
  });

  const spreadsheetXml = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Sophie AI - Ecofix</Author>
  <Created>${now.toISOString()}</Created>
  <Company>Ecofix Belgique</Company>
 </DocumentProperties>
 <Styles>
   ${xmlStyles}
 </Styles>
 <Worksheet ss:Name="Prospects Ecofix">
  <Table>
   <!-- Generous explicit widths: NO text cut off and ZERO "#####" -->
   <Column ss:Width="130"/> <!-- Nom -->
   <Column ss:Width="130"/> <!-- Prénom -->
   <Column ss:Width="120"/> <!-- Téléphone -->
   <Column ss:Width="180"/> <!-- Email -->
   <Column ss:Width="150"/> <!-- Statut -->
   <Column ss:Width="140"/> <!-- Région -->
   <Column ss:Width="130"/> <!-- GRD -->
   <Column ss:Width="140"/> <!-- Fournisseur -->
   <Column ss:Width="160"/> <!-- EAN -->
   <Column ss:Width="140"/> <!-- Date -->
   <Column ss:Width="120"/> <!-- ID -->

   <!-- Top Banner -->
   <Row ss:Height="30">
    <Cell ss:MergeAcross="10" ss:StyleID="BannerTitle">
      <Data ss:Type="String"> ECOFIX BELGIQUE • RAPPORT OFFICIEL DES PROSPECTS CRM (SOPHIE AI)</Data>
    </Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:MergeAcross="10" ss:StyleID="BannerMeta">
      <Data ss:Type="String">Généré le ${timeStamp} • Total : ${leads.length} prospects • Production Live Render • Données conformes RGPD</Data>
    </Cell>
   </Row>
   <Row ss:Height="8"/>

   <!-- Table Headers -->
   <Row ss:Height="26">
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Nom</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Prénom</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Téléphone</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Email</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Statut Commercial</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Région</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Gestionnaire de Réseau</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Fournisseur Actuel</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Code EAN</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Date d'Ajout</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">ID Prospect</Data></Cell>
   </Row>

   ${rowsXml}
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <Selected/>
   <FreezePanes/>
   <FrozenNoSplit/>
   <SplitPane>
    <Pane>
      <Number>3</Number>
     </Pane>
   </SplitPane>
   <ActiveRow>4</ActiveRow>
   <Panes>
    <Pane>
      <Number>3</Number>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
   <DisplayGridlines/>
  </WorksheetOptions>
 </Worksheet>
</Workbook>`;

  const blob = new Blob([spreadsheetXml], { type: "application/vnd.ms-excel;charset=utf-8;" });
  triggerDownload(blob, `prospects-ecofix-${dateStamp}.xls`);
};

// ==========================================
// 2. PERFORMANCE REPORT (CSV & EXCEL STYLISÉ)
// ==========================================

export const exportPerformanceToCsv = (
  overview: OverviewResponse | undefined,
  stats: StatsSummaryResponse | undefined,
  activities: ActivityFeedEntryResponse[] | undefined
) => {
  const now = new Date();
  const dateStamp = now.toISOString().slice(0, 10);
  const timeStamp = formatDisplayDate(now.toISOString());

  const lines: string[] = [
    `"=== ECOFIX BELGIQUE • RAPPORT DE SUPERVISION DES PERFORMANCES (SOPHIE AI) ===";""`,
    `"Date de génération";"${timeStamp}"`,
    `"Plateforme";"Production Render Live"`,
    `"Marché cible";"Énergie Belgique (Flandre & Wallonie)"`,
    `""`,
    `"=== INDICATEURS CLÉS DE PERFORMANCE (KPI) ===";""`,
    `"Indicateur";"Valeur";"Unité"`,
    `"Contacts Engagés";"${overview?.contacted ?? stats?.total_leads ?? 0}";"prospects"`,
    `"Conversations Actives";"${overview?.active_conversations ?? 0}";"conversations"`,
    `"Prospects Qualifiés";"${overview?.qualified ?? 0}";"prospects"`,
    `"Contrats Signés";"${overview?.signed_contracts ?? 0}";"contrats"`,
    `"Taux de Transformation";"${(overview?.conversion_rate ?? 0).toFixed(1)} %";"pourcentage"`,
    `"Coût d'Acquisition Client / Vente (CAC)";"${(overview?.cost_per_sale ?? 0).toFixed(2)} €";"euros"`,
    `"Chiffre d'Affaires Annuel Estimé (ARR)";"${(overview?.estimated_ca ?? 0).toLocaleString("fr-BE", { minimumFractionDigits: 2 })} €/an";"euros/an"`,
    `"Coût Moyen par Conversation";"${(overview?.cost_per_conversation ?? 0.02).toFixed(2)} €";"euros"`,
    `""`,
    `"=== ENTONNOIR DE CONVERSION COMMERCIALE ===";""`,
    `"Étape";"Volume";"Taux"`,
    `"01 - Nouveaux Contacts";"${overview?.total_leads ?? stats?.total_leads ?? 0}";"100 %"`,
    `"02 - Engagés par Sophie";"${overview?.contacted ?? 0}";"${overview?.total_leads ? Math.round(((overview.contacted || 0) / overview.total_leads) * 100) : 0} %"`,
    `"03 - Qualifiés (Flexy & Motion)";"${overview?.qualified ?? 0}";"${overview?.contacted ? Math.round(((overview.qualified || 0) / overview.contacted) * 100) : 0} %"`,
    `"04 - Contrats Signés";"${overview?.signed_contracts ?? 0}";"${overview?.qualified ? Math.round(((overview.signed_contracts || 0) / overview.qualified) * 100) : 0} %"`,
    `""`,
  ];

  if (stats?.by_status && Object.keys(stats.by_status).length > 0) {
    lines.push(`"=== RÉPARTITION DES STATUTS CRM ===";""`);
    lines.push(`"Statut";"Nombre de Prospects"`);
    for (const [st, count] of Object.entries(stats.by_status)) {
      lines.push(`"${STATUS_LABELS[st] || st}";"${count}"`);
    }
    lines.push(`""`);
  }

  if (activities && activities.length > 0) {
    lines.push(`"=== FLUX D'ACTIVITÉ RÉCENT ===";;;`);
    lines.push(`"Date & Heure";"Prospect";"Type d'activité";"Détails"`);
    activities.forEach((act) => {
      lines.push(
        [
          excelText(formatDisplayDate(act.created_at)),
          `"${(act.lead_name || "Prospect").replace(/"/g, '""')}"`,
          `"${(act.type || "").replace(/"/g, '""')}"`,
          `"${(act.details || "").replace(/"/g, '""')}"`,
        ].join(";")
      );
    });
    lines.push(`""`);
  }

  lines.push(`"=== CONFORMITÉ & MENTIONS LÉGALES ===";""`);
  lines.push(`"Régulateurs";"CWaPE (Wallonie) • VREG (Flandre) • Bruxelles BRUGEL non desservi"`);
  lines.push(`"Vérité tarifaire";"Frais fixes 60,00 €/an • Option Digi 5,99 €/mois (optionnelle) • 0 € frais de résiliation"`);
  lines.push(`"Données";"SPÉCIMEN / DÉMO - DONNÉES FICTIVES DE PROSPECTS"`);

  const csvContent = lines.join("\r\n");
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, `rapport-performance-sophie-${dateStamp}.csv`);
};

export const exportPerformanceToExcel = (
  overview: OverviewResponse | undefined,
  stats: StatsSummaryResponse | undefined,
  activities: ActivityFeedEntryResponse[] | undefined
) => {
  const now = new Date();
  const dateStamp = now.toISOString().slice(0, 10);
  const timeStamp = formatDisplayDate(now.toISOString());

  const xmlStyles = `
    <Style ss:ID="Default" ss:Name="Normal">
      <Alignment ss:Vertical="Center"/>
      <Font ss:FontName="Segoe UI" ss:Size="10" ss:Color="#0F172A"/>
    </Style>
    <Style ss:ID="BannerTitle">
      <Font ss:FontName="Segoe UI" ss:Size="14" ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center" ss:Indent="1"/>
    </Style>
    <Style ss:ID="BannerMeta">
      <Font ss:FontName="Segoe UI" ss:Size="9" ss:Color="#94A3B8"/>
      <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center" ss:Indent="1"/>
    </Style>
    <Style ss:ID="SectionHeader">
      <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#0F766E"/>
      <Interior ss:Color="#CCFBF1" ss:Pattern="Solid"/>
      <Alignment ss:Vertical="Center" ss:Indent="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#14B8A6"/>
      </Borders>
    </Style>
    <Style ss:ID="TableHeader">
      <Font ss:FontName="Segoe UI" ss:Size="10" ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#0D9488" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="2" ss:Color="#0F766E"/>
      </Borders>
    </Style>
    <Style ss:ID="KpiLabel">
      <Font ss:FontName="Segoe UI" ss:Size="10" ss:Bold="1" ss:Color="#1E293B"/>
      <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
    </Style>
    <Style ss:ID="KpiValue">
      <Font ss:FontName="Segoe UI" ss:Size="11" ss:Bold="1" ss:Color="#0F766E"/>
      <Interior ss:Color="#FFFFFF" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Right" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
    </Style>
    <Style ss:ID="CellEven">
      <Interior ss:Color="#FFFFFF" ss:Pattern="Solid"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
      <Alignment ss:Vertical="Center"/>
    </Style>
    <Style ss:ID="CellOdd">
      <Interior ss:Color="#F8FAFC" ss:Pattern="Solid"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#E2E8F0"/>
      </Borders>
      <Alignment ss:Vertical="Center"/>
    </Style>
  `;

  // Status breakdown rows
  let statusRows = "";
  if (stats?.by_status) {
    Object.entries(stats.by_status).forEach(([st, cnt], i) => {
      const style = i % 2 === 0 ? "CellEven" : "CellOdd";
      statusRows += `
        <Row ss:Height="20">
          <Cell ss:StyleID="${style}"><Data ss:Type="String">${escapeXml(STATUS_LABELS[st] || st)}</Data></Cell>
          <Cell ss:StyleID="${style}"><Data ss:Type="Number">${cnt}</Data></Cell>
        </Row>
      `;
    });
  }

  // Activities rows
  let actRows = "";
  if (activities && activities.length > 0) {
    activities.forEach((act, i) => {
      const style = i % 2 === 0 ? "CellEven" : "CellOdd";
      actRows += `
        <Row ss:Height="20">
          <Cell ss:StyleID="${style}"><Data ss:Type="String">${escapeXml(formatDisplayDate(act.created_at))}</Data></Cell>
          <Cell ss:StyleID="${style}"><Data ss:Type="String">${escapeXml(act.lead_name || "Prospect")}</Data></Cell>
          <Cell ss:StyleID="${style}"><Data ss:Type="String">${escapeXml(act.type || "")}</Data></Cell>
          <Cell ss:StyleID="${style}"><Data ss:Type="String">${escapeXml(act.details || "")}</Data></Cell>
        </Row>
      `;
    });
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Sophie AI - Ecofix</Author>
  <Created>${now.toISOString()}</Created>
  <Company>Ecofix Belgique</Company>
 </DocumentProperties>
 <Styles>
   ${xmlStyles}
 </Styles>
 <Worksheet ss:Name="Supervision Performances">
  <Table>
   <Column ss:Width="240"/>
   <Column ss:Width="160"/>
   <Column ss:Width="140"/>
   <Column ss:Width="260"/>

   <!-- Header -->
   <Row ss:Height="30">
    <Cell ss:MergeAcross="3" ss:StyleID="BannerTitle">
      <Data ss:Type="String"> ECOFIX BELGIQUE • RAPPORT DE SUPERVISION DES PERFORMANCES</Data>
    </Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:MergeAcross="3" ss:StyleID="BannerMeta">
      <Data ss:Type="String">Généré le ${timeStamp} • Production Render Live • Moteur Déterministe Certifié</Data>
    </Cell>
   </Row>
   <Row ss:Height="12"/>

   <!-- Section 1: KPI -->
   <Row ss:Height="24">
    <Cell ss:MergeAcross="3" ss:StyleID="SectionHeader">
      <Data ss:Type="String">1. INDICATEURS CLÉS DE PERFORMANCE (KPI)</Data>
    </Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Contacts Engagés (Total Leads)</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.contacted ?? stats?.total_leads ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">prospects</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Base qualifiée</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Conversations Actives</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.active_conversations ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">échanges</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Multi-canal (Web/Telegram/SMS)</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Prospects Qualifiés</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.qualified ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">prospects</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Flexy (variable) &amp; Motion (dynamique)</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Contrats Signés</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.signed_contracts ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">contrats</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Validation PDF &amp; Yousign</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Taux de Transformation</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="String">${(overview?.conversion_rate ?? 0).toFixed(1)} %</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">pourcentage</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Conversion globale</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Coût d'Acquisition Client / Vente (CAC)</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="String">${(overview?.cost_per_sale ?? 0).toFixed(2)} €</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">euros</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">&gt; 99% d'économie vs call center</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Chiffre d'Affaires Annuel Estimé (ARR)</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="String">${(overview?.estimated_ca ?? 0).toLocaleString("fr-BE", { minimumFractionDigits: 2 })} €/an</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">euros/an</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Frais fixes 60 €/an (+ option Digi)</Data></Cell>
   </Row>
   <Row ss:Height="22">
    <Cell ss:StyleID="KpiLabel"><Data ss:Type="String">Coût Moyen par Conversation</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="String">${(overview?.cost_per_conversation ?? 0.02).toFixed(2)} €</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">euros</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Inférence Groq ultra-rapide</Data></Cell>
   </Row>
   <Row ss:Height="14"/>

   <!-- Section 2: Funnel -->
   <Row ss:Height="24">
    <Cell ss:MergeAcross="3" ss:StyleID="SectionHeader">
      <Data ss:Type="String">2. ENTONNOIR DE VENTE (CONVERSION FUNNEL)</Data>
    </Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Étape du Tunnel</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Volume</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Progression</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Détails</Data></Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">01 - Nouveaux Contacts</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.total_leads ?? stats?.total_leads ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">100 %</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Imports CSV &amp; Web</Data></Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">02 - Engagés par Sophie</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.contacted ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">${overview?.total_leads ? Math.round(((overview.contacted || 0) / overview.total_leads) * 100) : 0} %</Data></Cell>
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">Salutations et conformité IA transmises</Data></Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">03 - Qualifiés (Flexy &amp; Motion)</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.qualified ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">${overview?.contacted ? Math.round(((overview.qualified || 0) / overview.contacted) * 100) : 0} %</Data></Cell>
    <Cell ss:StyleID="CellEven"><Data ss:Type="String">Critères d'éligibilité validés</Data></Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">04 - Contrats Signés</Data></Cell>
    <Cell ss:StyleID="KpiValue"><Data ss:Type="Number">${overview?.signed_contracts ?? 0}</Data></Cell>
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">${overview?.qualified ? Math.round(((overview.signed_contracts || 0) / overview.qualified) * 100) : 0} %</Data></Cell>
    <Cell ss:StyleID="CellOdd"><Data ss:Type="String">Prêts pour activation gestionnaire</Data></Cell>
   </Row>
   <Row ss:Height="14"/>

   ${statusRows ? `
   <Row ss:Height="24">
    <Cell ss:MergeAcross="3" ss:StyleID="SectionHeader">
      <Data ss:Type="String">3. RÉPARTITION DES STATUTS CRM</Data>
    </Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Statut CRM</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Nombre de Prospects</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">-</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">-</Data></Cell>
   </Row>
   ${statusRows}
   <Row ss:Height="14"/>
   ` : ''}

   ${actRows ? `
   <Row ss:Height="24">
    <Cell ss:MergeAcross="3" ss:StyleID="SectionHeader">
      <Data ss:Type="String">4. DERNIÈRES INTERACTIONS (FLUX D'ACTIVITÉ)</Data>
    </Cell>
   </Row>
   <Row ss:Height="20">
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Horodatage</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Prospect</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Type d'Événement</Data></Cell>
    <Cell ss:StyleID="TableHeader"><Data ss:Type="String">Détails</Data></Cell>
   </Row>
   ${actRows}
   ` : ''}

  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <Selected/>
   <DisplayGridlines/>
  </WorksheetOptions>
 </Worksheet>
</Workbook>`;

  const blob = new Blob([xml], { type: "application/vnd.ms-excel;charset=utf-8;" });
  triggerDownload(blob, `rapport-performance-sophie-${dateStamp}.xls`);
};

// XML escape helper
const escapeXml = (unsafe: string | number | null | undefined): string => {
  if (unsafe === null || unsafe === undefined) return "";
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
};
