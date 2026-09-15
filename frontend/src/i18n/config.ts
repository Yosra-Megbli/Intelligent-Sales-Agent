import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import fr from "./locales/fr.json";
import nl from "./locales/nl.json";
import en from "./locales/en.json";

const resources = {
  fr: { translation: fr },
  nl: { translation: nl },
  en: { translation: en },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "fr",
    lng: localStorage.getItem("sophie_language") || "fr",
    interpolation: {
      escapeValue: false, // React already safes from XSS
    },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "sophie_language",
      caches: ["localStorage"],
    },
  });

export default i18n;
