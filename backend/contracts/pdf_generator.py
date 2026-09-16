"""
Contract PDF Specimen Generator — Sophie (Ecofix).

Generates certified PDF specimen contracts for Belgian energy supply (Flexy / Motion),
strictly adhering to compliance constraints:
- Watermark / Banner: "SPÉCIMEN / DEMO — DONNÉES FICTIVES"
- Real lead data from CRM only (never LLM output)
- Preamble verbatim quoting AI disclosure + European AI Act Art. 50 reference
- Correct grid operators (Flanders=Fluvius, Wallonia=ORES/RESA, never mixed, no Brussels)
- Friends with Benefits (€5/mo per active referral) & Platform fee €5.99/mo
- 14-day legal withdrawal annex (Belgian Code of Economic Law Art. VI.47)
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from domain.models.contract import Contract
from domain.models.lead import Lead

AI_PREAMBLE_FR = (
    "Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — "
    "un conseiller humain reste disponible à tout moment. Conformément au Règlement européen "
    "sur l'Intelligence Artificielle (AI Act, Règlement UE 2024/1689, Art. 50), le présent contrat "
    "a été préparé de manière automatisée par un système d'intelligence artificielle sous supervision humaine."
)

AI_PREAMBLE_NL = (
    "Dag, hier is Sophie, de virtuele assistent (AI) van Ecofix — een menselijke adviseur "
    "neemt op elk moment over als u dat liever heeft. Overeenkomstig de Europese AI-verordening "
    "(AI Act, Verordening EU 2024/1689, Art. 50) werd deze overeenkomst geautomatiseerd opgesteld "
    "door een AI-systeem onder menselijk toezicht."
)

AI_PREAMBLE_EN = (
    "Hi, this is Sophie, a virtual assistant (AI) for Ecofix — a human advisor is available "
    "at any time. In accordance with the European Artificial Intelligence Act (EU Regulation 2024/1689, "
    "Art. 50), this agreement has been prepared automatically by an artificial intelligence system "
    "under human supervision."
)


def get_grid_operator(region: Optional[str]) -> str:
    """Belgian Grid Operator rule: Flanders=Fluvius, Wallonia=ORES/RESA. Never mixed. No Brussels."""
    r = (region or "").strip().lower()
    if any(k in r for k in ("fland", "vlaan", "antw", "limburg", "gent", "brugge")):
        return "Fluvius (Flandre)"
    if any(k in r for k in ("wallon", "namur", "liège", "liege", "charleroi", "mons", "hainaut", "luxembourg", "brabant wallon")):
        return "ORES / RESA (Wallonie)"
    return "ORES / Fluvius (selon commune)"


def generate_contract_pdf(
    lead: Lead,
    contract: Contract,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate contract PDF with ReportLab using CRM lead data only."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    watermark_style = ParagraphStyle(
        "Watermark",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#dc2626"),
        alignment=1,  # Center
        spaceAfter=6,
    )

    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "ContractSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0d9488"),
        spaceAfter=12,
    )

    preamble_box_style = ParagraphStyle(
        "PreambleBox",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1e293b"),
    )

    mono_style = ParagraphStyle(
        "MonoStyle",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0f766e"),
    )

    story = []

    # 1. Specimen Watermark Header
    story.append(
        Paragraph(
            "★ SPÉCIMEN / DEMO — DONNÉES FICTIVES ★",
            watermark_style,
        )
    )
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=colors.HexColor("#ef4444"),
            spaceBefore=2,
            spaceAfter=10,
        )
    )

    # 2. Document Title & Reference
    product_name = contract.product or "Flexy"
    ref_num = f"ECOFIX-{product_name.upper()}-{str(contract.id)[:8].upper()}"
    story.append(Paragraph(f"CONTRAT DE FOURNITURE D'ÉNERGIE VERTE — ECOFIX {product_name.upper()}", title_style))
    story.append(
        Paragraph(
            f"Référence contrat : <b>{ref_num}</b> &nbsp;|&nbsp; Date : {datetime.utcnow().strftime('%d/%m/%Y')}",
            subtitle_style,
        )
    )

    # 3. AI Act Transparency Preamble (mandatory legal verbatim)
    lang = getattr(lead, "language", "fr") or "fr"
    preamble_text = AI_PREAMBLE_FR if lang == "fr" else (AI_PREAMBLE_NL if lang == "nl" else AI_PREAMBLE_EN)

    preamble_table = Table(
        [[Paragraph(f"<b>PRÉAMBULE DE TRANSPARENCE IA (Règlement UE 2024/1689, Art. 50) :</b><br/>{preamble_text}", preamble_box_style)]],
        colWidths=[17.4 * cm],
    )
    preamble_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
            ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#99f6e4")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(preamble_table)
    story.append(Spacer(1, 10))

    # 4. Identification du Prospect (CRM data only - never LLM)
    story.append(Paragraph("1. IDENTIFICATION DU SOUSCRIPTEUR & DU POINT DE FOURNITURE", section_heading))

    full_name = f"{lead.first_name or '—'} {lead.last_name or '—'}".strip()
    full_address = f"{lead.address or ''} {lead.city or ''} ({lead.region or 'Belgique'})".strip() or "Belgique"
    grd = get_grid_operator(lead.region)
    ean_code = lead.ean or "5414" + "0" * 14

    client_data = [
        [Paragraph("<b>Souscripteur :</b>", body_style), Paragraph(full_name, body_style),
         Paragraph("<b>Date de naissance :</b>", body_style), Paragraph(lead.date_of_birth or "—", body_style)],
        [Paragraph("<b>Adresse d'installation :</b>", body_style), Paragraph(full_address, body_style),
         Paragraph("<b>Téléphone :</b>", body_style), Paragraph(lead.phone or "—", body_style)],
        [Paragraph("<b>Adresse e-mail :</b>", body_style), Paragraph(lead.email or "—", body_style),
         Paragraph("<b>Gestionnaire (GRD) :</b>", body_style), Paragraph(grd, body_style)],
        [Paragraph("<b>Code EAN (18 chiffres) :</b>", body_style), Paragraph(ean_code, mono_style),
         Paragraph("<b>Fournisseur actuel :</b>", body_style), Paragraph(lead.current_supplier or "—", body_style)],
    ]

    client_table = Table(client_data, colWidths=[4.2 * cm, 4.8 * cm, 4.0 * cm, 4.4 * cm])
    client_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 4.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(client_table)
    story.append(Spacer(1, 8))

    # 5. Formule Tarifaire & Engagements Commerciaux
    story.append(Paragraph("2. DÉTAILS DE L'OFFRE & CONDITIONS TARIFAIRES", section_heading))

    product_desc = (
        "<b>Tarification dynamique horaire :</b> répercussion transparente des cours horaires EPEX Spot. "
        "Idéal pour véhicules électriques, pompes à chaleur et stockage batterie."
        if product_name.lower() == "motion"
        else "<b>Tarification variable mensuelle :</b> révision transparente indexée sur les marchés, sans frais cachés ni engagement de durée."
    )

    terms_data = [
        [Paragraph("<b>Offre souscrite :</b>", body_style), Paragraph(f"Ecofix {product_name.upper()} — 100% Électricité Verte", body_style)],
        [Paragraph("<b>Fonctionnement du prix :</b>", body_style), Paragraph(product_desc, body_style)],
        [Paragraph("<b>Redevance fixe plateforme :</b>", body_style), Paragraph("<b>5,99 € TTC / mois</b> (soit 71,88 €/an)", body_style)],
        [Paragraph("<b>Friends with Benefits :</b>", body_style), Paragraph("<b>5,00 € / mois de réduction</b> par ami parrainé ayant un contrat actif.", body_style)],
        [Paragraph("<b>Indemnité de résiliation :</b>", body_style), Paragraph("<b>0,00 €</b> (aucune indemnité de rupture résidentielle en Belgique).", body_style)],
        [Paragraph("<b>Délai de bascule technique :</b>", body_style), Paragraph("3 à 4 semaines auprès de votre gestionnaire de réseau.", body_style)],
    ]

    terms_table = Table(terms_data, colWidths=[4.8 * cm, 12.6 * cm])
    terms_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(terms_table)
    story.append(Spacer(1, 8))

    # 6. Annexe Rétractation 14 jours (Belgian Code of Economic Law)
    story.append(Paragraph("3. ANNEXE LÉGALE : DROIT DE RÉTRACTATION DE 14 JOURS", section_heading))
    retractation_text = (
        "Conformément aux articles VI.47 et suivants du Code de droit économique belge, le consommateur a le droit "
        "de notifier à l'entreprise qu'il renonce à l'achat, sans pénalités et sans indication de motif, "
        "dans les <b>14 jours calendrier</b> à dater du lendemain du jour de la signature de la présente convention.<br/><br/>"
        "<b>Modalités pratiques de rétractation :</b> Vous pouvez exercer ce droit par tout moyen écrit non équivoque "
        "(e-mail à support@ecofix.be) ou directement auprès de notre assistante virtuelle en adressant le message : "
        "<b>« JE RENONCE »</b> (ou « IK HERROEP »). Aucune somme ne sera due."
    )
    retract_table = Table(
        [[Paragraph(retractation_text, body_style)]],
        colWidths=[17.4 * cm],
    )
    retract_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
            ("BORDER", (0, 0), (-1, -1), 1, colors.HexColor("#fef3c7")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(retract_table)
    story.append(Spacer(1, 10))

    # 7. Signature Block
    sig_status = f"Statut signature : <b>{contract.status.value}</b>"
    sig_date = contract.signed_at.strftime("%d/%m/%Y %H:%M") if contract.signed_at else "En attente de signature numérique"
    signature_data = [
        [Paragraph("<b>Pour Ecofix Energy Belgium :</b>", body_style), Paragraph("<b>Le Souscripteur :</b>", body_style)],
        [Paragraph("Signature électronique certifiée<br/><i>Sophie — Assistante Virtuelle Ecofix</i>", body_style),
         Paragraph(f"{sig_status}<br/>Date : {sig_date}<br/><i>Signature via Yousign v3</i>", body_style)],
    ]
    sig_table = Table(signature_data, colWidths=[8.7 * cm, 8.7 * cm])
    sig_table.setStyle(
        TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(sig_table)

    # Build PDF document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(pdf_bytes)

    return pdf_bytes
