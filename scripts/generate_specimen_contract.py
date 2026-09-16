#!/usr/bin/env python3
"""
Generate specimen energy supply contract PDF for Ecofix / Sophie.
Used in Phase 2 Frontend demo to close the contract gap visually.
All data is FICTIONAL per AGENTS.md: 'SPÉCIMEN / DEMO — DONNÉES FICTIVES'.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to draw diagonal watermark, header line, and footer on all pages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_watermark_and_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_watermark_and_decorations(self, page_count):
        self.saveState()
        
        # 1. Diagonal Watermark
        self.setFont("Helvetica-Bold", 42)
        self.setFillColor(colors.HexColor("#E2E8F0"), alpha=0.35)
        self.translate(A4[0] / 2, A4[1] / 2)
        self.rotate(45)
        self.drawCentredString(0, 0, "SPÉCIMEN — DONNÉES FICTIVES")
        self.restoreState()

        # 2. Header
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(2 * cm, A4[1] - 1.5 * cm, "ECOFIX GAS & POWER BE — CONTRAT DE FOURNITURE")
        self.setFont("Helvetica", 8)
        self.drawRightString(A4[0] - 2 * cm, A4[1] - 1.5 * cm, "RÉF : SPECIMEN-2026-MOTION")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(2 * cm, A4[1] - 1.7 * cm, A4[0] - 2 * cm, A4[1] - 1.7 * cm)

        # 3. Footer
        self.setFont("Helvetica-Oblique", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        footer_text = "Document de démonstration — contrat réel généré en Phase 2 avec signature électronique (Yousign/DocuSign sandbox)"
        self.drawString(2 * cm, 1.4 * cm, footer_text)
        self.setFont("Helvetica", 8)
        self.drawRightString(A4[0] - 2 * cm, 1.4 * cm, f"Page {self._pageNumber} / {page_count}")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(2 * cm, 1.8 * cm, A4[0] - 2 * cm, 1.8 * cm)
        self.restoreState()


def generate_contract(output_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_navy = colors.HexColor("#0F172A")
    brand_teal = colors.HexColor("#0D9488")
    ink_dark = colors.HexColor("#1E293B")
    ink_muted = colors.HexColor("#475569")

    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=brand_navy,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "ContractSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=brand_teal,
        spaceAfter=14,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=15,
        textColor=brand_navy,
        spaceBefore=10,
        spaceAfter=5,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=ink_dark,
        spaceAfter=6,
    )

    quote_style = ParagraphStyle(
        "QuotePreamble",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12.5,
        textColor=brand_navy,
        leftIndent=12,
        rightIndent=12,
        spaceBefore=4,
        spaceAfter=8,
    )

    story = []

    # Title
    story.append(Paragraph("CONTRAT DE FOURNITURE D'ÉNERGIE — SPÉCIMEN", title_style))
    story.append(Paragraph("OFFRE TARIFAIRE DYNAMIQUE : ECOFIX MOTION (ÉLECTRICITÉ 100% VERTE)", subtitle_style))

    # Preambule quoting Sophie's disclosure verbatim
    story.append(Paragraph("PRÉAMBULE & DIVULGATION DE TRANSPARENCE IA", section_heading))
    preamble_text = (
        "Le présent document fait suite aux échanges interactifs d'information et de qualification menés par "
        "l'assistante commerciale automatisée de la société Ecofix Gas & Power BE. "
        "Conformément aux exigences de transparence de l'AI Act européen (Règlement UE 2024/1689), le souscripteur "
        "a été expressément informé dès l'ouverture de la session par la mention certifiée suivante :"
    )
    story.append(Paragraph(preamble_text, body_style))
    story.append(Paragraph(
        "« Bonjour, ici Sophie, assistante virtuelle (intelligence artificielle) d'Ecofix — "
        "un conseiller humain reste disponible à tout moment. »",
        quote_style,
    ))

    # Parties Table
    story.append(Paragraph("1. LES PARTIES AU CONTRAT", section_heading))
    parties_data = [
        [
            Paragraph("<b>LE FOURNISSEUR :</b><br/>Ecofix Gas & Power BE SA<br/>Avenue Louise 240, 1050 Bruxelles<br/>BCE : 0845.992.120 — TVA : BE0845.992.120<br/>Service client : contact@ecofix.be", body_style),
            Paragraph("<b>LE CLIENT SOUSCRIPTEUR (FICTIF) :</b><br/>Monsieur Jef Peeters<br/>Dorpstraat 45<br/>2850 Boom (Flandre, Belgique)<br/>Email : jef.peeters@demo.ecofix.be<br/>Tél : +32 470 12 34 56", body_style),
        ]
    ]
    parties_table = Table(parties_data, colWidths=[8.5 * cm, 8.5 * cm])
    parties_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 6))

    # Point de fourniture & Produit
    story.append(Paragraph("2. POINT DE FOURNITURE & JUSTIFICATION DU PRODUIT", section_heading))
    points_data = [
        [Paragraph("<b>Code EAN Électricité (18 chiffres) :</b>", body_style), Paragraph("<b>5414 0001 2345 6789 01</b> (Fictif)", body_style)],
        [Paragraph("<b>Gestionnaire de Réseau de Distribution (GRD) :</b>", body_style), Paragraph("Fluvius (Flandre)", body_style)],
        [Paragraph("<b>Produit souscrit :</b>", body_style), Paragraph("<b>Ecofix Motion</b> (Tarification horaire dynamique)", body_style)],
        [Paragraph("<b>Justification d'éligibilité produit :</b>", body_style), Paragraph("Le client déclare posséder un <b>véhicule électrique (EV)</b> et/ou une pompe à chaleur, maximisant les économies lors des heures creuses et de production renouvelable abondante.", body_style)],
    ]
    points_table = Table(points_data, colWidths=[6.5 * cm, 10.5 * cm])
    points_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(points_table)
    story.append(Spacer(1, 6))

    # Conditions tarifaires
    story.append(Paragraph("3. CONDITIONS TARIFAIRES & FRAIS FIXES", section_heading))
    tarifs_text = (
        "Le contrat <b>Ecofix Motion</b> est indexé directement sur les cotations horaires de la bourse de l'électricité "
        "EPEX SPOT Belgique Day-Ahead, répercutées sans majoration opaque. "
        "Des frais fixes annuels obligatoires de <b>60,00 € / an TTC</b> (soit 5,00 € / mois) sont appliqués. "
        "L'application mobile Ecofix Digi pour le suivi intelligent et le pilotage des consommations est disponible en option facultative à <b>5,99 € / mois TTC</b>."
    )
    story.append(Paragraph(tarifs_text, body_style))

    # Programme Parrainage
    story.append(Paragraph("4. PROGRAMME AVANTAGE « FRIENDS WITH BENEFITS »", section_heading))
    fwb_text = (
        "Dans le cadre de l'offre Ecofix, le souscripteur bénéficie d'une déduction de <b>5,00 € / mois</b> sur sa facture "
        "pour chaque filleul actif souscrivant une offre résidentielle via son lien exclusif, sans limite de cumul dans la limite "
        "de la facture de redevance annuelle."
    )
    story.append(Paragraph(fwb_text, body_style))

    # Durée, Résiliation et Droit de Rétractation
    story.append(Paragraph("5. DURÉE, RÉSILIATION ET DROIT DE RÉTRACTATION (CADRE LÉGAL BELGE)", section_heading))
    legal_text = (
        "<b>Aucuns frais de résiliation :</b> Conformément à la législation belge régissant le marché de l'énergie pour les clients "
        "résidentiels et petits professionnels, le client peut résilier le présent contrat à tout moment sans indemnité de rupture, "
        "moyennant le respect du préavis légal de transfert de 3 à 4 semaines auprès de son nouveau fournisseur.<br/>"
        "<b>Droit de rétractation :</b> Le consommateur dispose d'un délai légal de <b>14 jours calendrier</b> à compter de la confirmation "
        "de souscription pour exercer son droit de rétractation sans motif ni pénalité en notifiant Ecofix par simple courrier ou email."
    )
    story.append(Paragraph(legal_text, body_style))

    # Signatures
    story.append(Spacer(1, 10))
    story.append(Paragraph("6. ENGAGEMENT DES PARTIES & SIGNATURE ÉLECTRONIQUE", section_heading))
    sig_data = [
        [
            Paragraph("<b>Pour Ecofix Gas & Power BE SA :</b><br/><br/>Direction Commerciale<br/><i>Contrat validé électroniquement</i>", body_style),
            Paragraph("<b>Pour le Client (Fictif) :</b><br/><br/>Jef Peeters<br/><i>Document de spécimen — Non soumis à signature</i>", body_style),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] Specimen contract generated at: {output_path}")

if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "contrat-specimen.pdf")
    generate_contract(target)
