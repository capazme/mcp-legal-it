/* Synthetic excerpt in the shape of connect.facebook.net/signals/config/<ID> (invented pixel ID). */
fbq.registerPlugin("config:1111111111111111", {__fbEventsPlugin: 1, plugin: function(fbq, instance, config) {
config.set("1111111111111111", "inferredEvents", {"buttonSelector":null,"disableRestrictedData":false});
config.set("1111111111111111", "automaticMatching", {"selectedMatchKeys":["em","ph","fn","ln","db"]});
config.set("1111111111111111", "unwantedData", {"blacklisted_keys":{"PageView":{"cd":[],"url":["email_address"]}},"sensitive_keys":{}});
instance.optIn("1111111111111111", "InferredEvents", true);
instance.optIn("1111111111111111", "AutomaticMatching", true);
instance.optIn("1111111111111111", "FirstPartyCookies", true);
instance.optIn("1111111111111111", "UnwantedData", true);
}});
