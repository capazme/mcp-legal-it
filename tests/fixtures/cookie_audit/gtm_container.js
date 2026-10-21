// Copyright 2012 Google Inc. All rights reserved.
// Synthetic container for tests/unit/test_cookie_audit_pixels.py: same structure as a
// real gtm.js (resource / permissions), every ID and domain invented.
(function(){

var data = {
"resource": {
  "version":"7",
  "macros":[
    {"function":"__e"},
    {"function":"__k","vtp_name":"OptanonConsent","vtp_decodeCookie":false},
    {"function":"__c","vtp_value":"1234567890123456"},
    {"function":"__v","vtp_name":"user_email","vtp_dataLayerVersion":2},
    {"function":"__awec","vtp_mode":"MANUAL","vtp_email":["macro",3]}
  ],
  "tags":[
    {"function":"__cvt_ABCDE","once_per_event":true,"vtp_pixelId":["macro",2],"vtp_standardEventName":"PageView","vtp_eventName":"standard","vtp_advancedMatching":true,"vtp_advancedMatchingList":["list",["map","name","em","value",["macro",3]]],"vtp_consent":true,"tag_id":10},
    {"function":"__html","once_per_event":true,"vtp_html":"<script>!function(f,b,e,v){}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','6543210987654321');fbq('track','PageView');</script>","vtp_supportDocumentWrite":false,"tag_id":11},
    {"function":"__awct","consent":["list","ad_storage","ad_user_data"],"once_per_event":true,"vtp_conversionId":"123456789","vtp_conversionLabel":"AbCdEf","vtp_enableEnhancedConversionsCheckbox":false,"tag_id":12},
    {"function":"__baut","once_per_load":true,"vtp_tagId":"98765432","vtp_eventType":"PAGE_LOAD","vtp_c_consentInheritGtm":true,"tag_id":13},
    {"function":"__html","setup_tags":["list",["tag",3,0]],"once_per_event":true,"vtp_html":"<script>window.uetq=window.uetq||[];window.uetq.push('event','purchase',{});</script>","tag_id":14},
    {"function":"__img","once_per_event":true,"vtp_url":"https://pixel.esempio-adnet.example/p.gif?cid=42","tag_id":15},
    {"function":"__cvt_CONSM","once_per_event":true,"vtp_command":"default","vtp_ad_storage":"denied","vtp_analytics_storage":"granted","vtp_ad_user_data":"denied","vtp_ad_personalization":"denied","vtp_wait_for_update":"500","tag_id":16},
    {"function":"__paused","vtp_originalTagType":"pntr","tag_id":17},
    {"function":"__cl","tag_id":18},
    {"function":"__googtag","vtp_tagId":"G-ABCDEF1234","vtp_userProperties":["list",["map","name","md5email","value",["macro",3]]],"tag_id":19}
  ],
  "predicates":[
    {"function":"_eq","arg0":["macro",0],"arg1":"gtm.js"},
    {"function":"_cn","arg0":["macro",1],"arg1":"C0004:0"},
    {"function":"_re","arg0":["macro",0],"arg1":".*"},
    {"function":"_eq","arg0":["macro",0],"arg1":"purchase"},
    {"function":"_eq","arg0":["macro",0],"arg1":"gtm.init_consent"}
  ],
  "rules":[
    [["if",0],["add",0,1,5,9]],
    [["if",1,2],["block",0]],
    [["if",3],["add",2,4]],
    [["if",4],["add",6]]
  ]
},
"runtime":[],
"permissions":{
  "__cvt_ABCDE":{"inject_script":{"urls":["https://connect.facebook.net/en_US/fbevents.js"]},"access_globals":{"keys":[{"key":"fbq","read":true,"write":true,"execute":false},{"key":"_fbq_gtm","read":true,"write":true,"execute":false}]}},
  "__cvt_CONSM":{"access_consent":{"consentTypes":[{"consentType":"ad_storage","read":true,"write":true}]}}
},
"sandboxed_scripts":[],
"security_groups":{}
};

/* the container runtime that follows `data` in a real gtm.js is omitted here */
})();
