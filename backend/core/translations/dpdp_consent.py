# core/translations/dpdp_consent.py
"""DPDP Act consent gate (hospitals.dpdp_consent_required, default off) --
shown right after language selection, before any patient identity is
resolved, for a hospital that has turned this on. Only "I Agree" is ever
persisted (db/schema.sql's own comment on dpdp_consents explains why); the
exact copy in dpdp_consent_body was given verbatim, not drafted -- do not
reword without checking with the user first, since this is compliance-facing
text.

Also holds Section 20's "Consent & Privacy" menu item -- kept intentionally
minimal (a real status display + one genuine toggle, not a full legal
consent-management platform). Service consent and marketing consent are
shown/controlled separately, never bundled, per the doc's own explicit
instruction."""
from core.translations._common import Language

STRINGS: dict[str, dict[Language, str]] = {
    "dpdp_consent_body": {
        "en": (
            "Welcome to the {hospital_name} Booking Bot!\n\n"
            "Your privacy is important to us. In compliance with the Digital Personal Data Protection (DPDP) Act, "
            "we need your explicit consent before we begin:\n\n"
            "* We will securely store your name, phone number, age, and doctor preferences to manage your "
            "appointments and send medical reminders.\n"
            "* Your data remains strictly confidential and will never be shared with third parties.\n"
            # "* You can request the removal of your data at any time by texting \"DELETE\".\n\n"
            "Please select an option below to proceed:"
        ),
        "hi": (
            "नमस्ते! {hospital_name} बुकिंग बोट में आपका स्वागत है।\n\n"
            "आपकी गोपनीयता हमारे लिए महत्वपूर्ण है। डिजिटल व्यक्तिगत डेटा संरक्षण (DPDP) अधिनियम के तहत, "
            "आगे बढ़ने से पहले हमें आपकी सहमति की आवश्यकता है:\n\n"
            "* हम आपका नाम, फ़ोन नंबर, उम्र और डॉक्टर की पसंद जैसी जानकारी आपके अपॉइंटमेंट बुक करने और आपको "
            "मेडिकल रिमाइंडर भेजने के लिए सुरक्षित रूप से जमा (store) करेंगे।\n"
            "* आपका डेटा पूरी तरह से सुरक्षित रहेगा और इसे किसी बाहरी संस्था के साथ साझा (share) नहीं किया जाएगा।\n"
            "* आप जब चाहें \"DELETE\" लिखकर अपना डेटा हटाने का अनुरोध कर सकते हैं।\n\n"
            "आगे बढ़ने के लिए कृपया नीचे दिए गए विकल्पों में से एक चुनें:"
        ),
    },
    "dpdp_agree_button": {"en": "I Agree", "hi": "मैं सहमत हूँ"},
    "dpdp_decline_button": {"en": "I Do Not Agree", "hi": "मैं सहमत नहीं हूँ"},
    "dpdp_declined_message": {
        "en": "We understand — but to keep your information safe, we do need your consent to our data privacy "
              "(DPDP) terms before we can continue. Let's start over: please pick your language below whenever "
              "you're ready to agree.",
        "hi": "हम समझते हैं — लेकिन आपकी जानकारी सुरक्षित रखने के लिए, आगे बढ़ने से पहले हमें डेटा गोपनीयता (DPDP) "
              "शर्तों पर आपकी सहमति चाहिए। आइए फिर से शुरू करें: जब आप सहमत होने के लिए तैयार हों, तो नीचे अपनी भाषा चुनें।",
    },

    "privacy_notice_default": {
        "en": "We use WhatsApp to help manage your appointments and hospital communication. "
              "Your information is used only for the services you request and is not shared with third parties "
              "without your consent.",
        "hi": "हम आपकी अपॉइंटमेंट और अस्पताल संचार प्रबंधित करने के लिए व्हाट्सएप का उपयोग करते हैं। "
              "आपकी जानकारी केवल आपके अनुरोध की गई सेवाओं के लिए उपयोग की जाती है और आपकी सहमति के बिना "
              "किसी तीसरे पक्ष के साथ साझा नहीं की जाती।",
    },
    "consent_privacy_body": {
        "en": "*Privacy Notice*\n{notice}\n\n*Consent Status*\nMarketing messages: {marketing_status}",
        "hi": "*गोपनीयता सूचना*\n{notice}\n\n*सहमति की स्थिति*\nमार्केटिंग संदेश: {marketing_status}",
    },
    "consent_on": {"en": "Enabled", "hi": "सक्षम"},
    "consent_off": {"en": "Disabled", "hi": "अक्षम"},
    "consent_marketing_enable": {"en": "Enable Marketing", "hi": "मार्केटिंग चालू करें"},
    "consent_marketing_disable": {"en": "Disable Marketing", "hi": "मार्केटिंग बंद करें"},
}
