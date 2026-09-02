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


DPDP_CONSENT_BODY = "dpdp_consent_body"
DPDP_AGREE_BUTTON = "dpdp_agree_button"
DPDP_DECLINE_BUTTON = "dpdp_decline_button"
DPDP_DECLINED_MESSAGE = "dpdp_declined_message"
PRIVACY_NOTICE_DEFAULT = "privacy_notice_default"
CONSENT_PRIVACY_BODY = "consent_privacy_body"
CONSENT_ON = "consent_on"
CONSENT_OFF = "consent_off"
CONSENT_MARKETING_ENABLE = "consent_marketing_enable"
CONSENT_MARKETING_DISABLE = "consent_marketing_disable"

STRINGS: dict[str, dict[Language, str]] = {
    DPDP_CONSENT_BODY: {
        # Previous body (kept for reference, not deleted -- see this
        # module's docstring on why this copy isn't reworded casually):
        # "en": (
        #     "Welcome to the {hospital_name} Booking Bot!\n\n"
        #     "Your privacy is important to us. In compliance with the Digital Personal Data Protection (DPDP) Act, "
        #     "we need your explicit consent before we begin:\n\n"
        #     "* We will securely store your name, phone number, age, and doctor preferences to manage your "
        #     "appointments and send medical reminders.\n"
        #     "* Your data remains strictly confidential and will never be shared with third parties.\n"
        #     "* You can request the removal of your data at any time by texting \"DELETE\".\n\n"
        #     "Please select an option below to proceed:"
        # ),
        "en": (
            "🔐 Your Privacy Matters\n\n"
            "To book and manage your appointment, {hospital_name} may collect information such as your name, "
            "mobile number, age, appointment details and doctor preference.\n\n"
            "Your information will be processed for appointment booking, healthcare-related services, "
            "communication and reminders in accordance with our Privacy Notice, applicable data-protection "
            "requirements and the Digital Personal Data Protection Act, 2023 (DPDP Act).\n\n"
            "You may withdraw your consent and exercise applicable privacy rights as described in our Privacy "
            "Notice.\n\n"
            "🔗 Privacy Notice: [link]\n\n"
            "By selecting I Agree, you consent to the processing described above."
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
    DPDP_AGREE_BUTTON: {"en": "I Agree", "hi": "मैं सहमत हूँ"},
    DPDP_DECLINE_BUTTON: {"en": "I Do Not Agree", "hi": "मैं सहमत नहीं हूँ"},
    DPDP_DECLINED_MESSAGE: {
        # Previous body (kept for reference, not deleted -- see this
        # module's docstring on why this copy isn't reworded casually):
        # "en": "We understand — but to keep your information safe, we do need your consent to our data privacy "
        #       "(DPDP) terms before we can continue. Let's start over: please pick your language below whenever "
        #       "you're ready to agree.",
        "en": (
            "We respect your choice.\n\n"
            "We will not continue with the WhatsApp appointment-booking process.\n\n"
            "You may contact {hospital_name} Reception for alternative assistance.\n\n"
            "☎️ +91 XXXXX XXXXX\n\n"
            "You can review our Privacy Notice here:\n"
            "[Privacy Notice]"
        ),
        # Previous body (kept for reference, not deleted -- see this
        # module's docstring on why this copy isn't reworded casually):
        # "hi": "हम समझते हैं — लेकिन आपकी जानकारी सुरक्षित रखने के लिए, आगे बढ़ने से पहले हमें डेटा गोपनीयता (DPDP) "
        #       "शर्तों पर आपकी सहमति चाहिए। आइए फिर से शुरू करें: जब आप सहमत होने के लिए तैयार हों, तो नीचे अपनी भाषा चुनें।",
        "hi": (
            "हम आपकी पसंद का सम्मान करते हैं।\n\n"
            "हम व्हाट्सएप अपॉइंटमेंट-बुकिंग प्रक्रिया को आगे नहीं बढ़ाएंगे।\n\n"
            "वैकल्पिक सहायता के लिए आप {hospital_name} रिसेप्शन से संपर्क कर सकते हैं।\n\n"
            "☎️ +91 XXXXX XXXXX\n\n"
            "आप हमारी गोपनीयता सूचना यहाँ देख सकते हैं:\n"
            "[Privacy Notice]"
        ),
    },

    PRIVACY_NOTICE_DEFAULT: {
        "en": "We use WhatsApp to help manage your appointments and hospital communication. "
              "Your information is used only for the services you request and is not shared with third parties "
              "without your consent.",
        "hi": "हम आपकी अपॉइंटमेंट और अस्पताल संचार प्रबंधित करने के लिए व्हाट्सएप का उपयोग करते हैं। "
              "आपकी जानकारी केवल आपके अनुरोध की गई सेवाओं के लिए उपयोग की जाती है और आपकी सहमति के बिना "
              "किसी तीसरे पक्ष के साथ साझा नहीं की जाती।",
    },
    CONSENT_PRIVACY_BODY: {
        "en": "*Privacy Notice*\n{notice}\n\n*Consent Status*\nMarketing messages: {marketing_status}",
        "hi": "*गोपनीयता सूचना*\n{notice}\n\n*सहमति की स्थिति*\nमार्केटिंग संदेश: {marketing_status}",
    },
    CONSENT_ON: {"en": "Enabled", "hi": "सक्षम"},
    CONSENT_OFF: {"en": "Disabled", "hi": "अक्षम"},
    CONSENT_MARKETING_ENABLE: {"en": "Enable Marketing", "hi": "मार्केटिंग चालू करें"},
    CONSENT_MARKETING_DISABLE: {"en": "Disable Marketing", "hi": "मार्केटिंग बंद करें"},
}
