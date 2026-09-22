// ============================================================
// SP PH Truck Booking — Google Sheets Auto-Sync
// ============================================================
// SETUP:
// 1. Open Google Sheets → Extensions → Apps Script
// 2. Paste this entire script into Code.gs
// 3. Set BACKEND_URL below to your deployed backend URL
// 4. Run setupSheets() once to create all tabs
// 5. Run installTrigger() once to enable hourly auto-sync
// ============================================================

var BACKEND_URL = "https://sp-truck-booking--dev.ninjavan.apps.substrait.build";

var SECTIONS = [
  { key: "masterlist",    sheet: "Masterlist",           endpoint: "/api/sync/masterlist" },
  { key: "fleet",         sheet: "Fleet",                endpoint: "/api/sync/fleet" },
  { key: "rates",         sheet: "Rate Management",      endpoint: "/api/sync/rates" },
  { key: "evaluation",    sheet: "Vendor Speed Performance", endpoint: "/api/sync/evaluation" },
  { key: "cost",          sheet: "Cost Analysis",        endpoint: "/api/sync/cost" },
  { key: "ports",         sheet: "Ports",                endpoint: "/api/sync/ports" },
  { key: "accounts",      sheet: "Accounts",             endpoint: "/api/sync/accounts" },
  { key: "departments",   sheet: "Departments",          endpoint: "/api/sync/departments" },
  { key: "packaging",     sheet: "Packaging",            endpoint: "/api/sync/packaging" },
  { key: "statuses",      sheet: "Statuses",             endpoint: "/api/sync/statuses" },
  { key: "truck-types",   sheet: "Truck Types",          endpoint: "/api/sync/truck-types" },
  { key: "vendors",       sheet: "Vendors",              endpoint: "/api/sync/vendors" }
];

var HEADERS = {
  "Masterlist": [
    "Request #","Requestor Name","Requestor Email","Account","Department",
    "Origin Port","Destination Port","Truck Type","Packaging","Quantity",
    "Vendor","Plate #","Trip ID","Drop #","Distance (KM)",
    "Booking Date","Pickup","Status",
    "Est. Cost","Actual Cost","Foul Trip Reason",
    "Helper Name","Arrived Dest Datetime","End Unloading Datetime",
    "Attachments","Notes","Delivery Remarks",
    "Updated By","Updated By Email","Updated At","Created At"
  ],
  "Fleet": [
    "Plate #","Truck Type","Vendor","Driver Name","Driver Phone","Helper Name",
    "Status","Capacity","Is Active","Current Requests","History Count","Created At"
  ],
  "Rate Management": [
    "Vendor","Truck Type","Origin Port","Destination Port",
    "Rate/Trip","Default Rate","Effective Date","Expiry Date","Is Active","Created At"
  ],
  "Vendor Speed Performance": [
    "Request #","Trip ID","Drop #","Distance (KM)","Account","Department",
    "Origin Port","Destination Port","Truck Type","Vendor",
    "Booking Date","Status",
    "Customs to Arrival","Pickup to Arrival",
    "Arrival to Start Load","Start to End Load",
    "End Load to Arrived Dest","Arrived to Start Unload",
    "Start to End Unload","Full Leg"
  ],
  "Cost Analysis": [
    "Request #","Trip ID","Distance (KM)","Origin Port","Destination Port",
    "Truck Type","Vendor","Plate #",
    "Booking Date","Pickup",
    "Est. Cost","Actual Cost","Status","Foul Trip Reason"
  ],
  "Ports":        ["ID","Name","Code","Address","Latitude","Longitude","Is Active","Created At"],
  "Accounts":     ["ID","Name","Code","Is Active","Created At"],
  "Departments":  ["ID","Name","Code","Is Active","Created At"],
  "Packaging":    ["ID","Name","Code","Is Active","Created At"],
  "Statuses":     ["ID","Name","Color","Is Active","Created At"],
  "Truck Types":  ["ID","Name","Code","Max KG","Max CBM","Capacities","Is Active","Created At"],
  "Vendors":      ["ID","Name","Contact Person","Phone","Email","Address","Is Active","Created At"]
};

var NESTED_FIELDS = {
  "Masterlist": {
    "Request #": "request_number",
    "Requestor Name": "requestor_name",
    "Requestor Email": "requestor_email",
    "Account": "account_name",
    "Department": "department_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Truck Type": "truck_type_name",
    "Packaging": "packaging_type_name",
    "Quantity": "quantity",
    "Vendor": "vendor_name",
    "Plate #": "plate_number",
    "Trip ID": "trip_id",
    "Drop #": "drop_sequence",
    "Distance (KM)": "distance_km",
    "Booking Date": "booking_date",
    "Pickup": "pickup_datetime",
    "Status": "status_name",
    "Est. Cost": "estimated_cost",
    "Actual Cost": "actual_cost",
    "Foul Trip Reason": "foul_trip_reason",
    "Helper Name": "helper_name",
    "Arrived Dest Datetime": "arrived_dest_datetime",
    "End Unloading Datetime": "end_unloading_datetime",
    "Attachments": "attachments",
    "Notes": "notes",
    "Delivery Remarks": "delivery_remarks",
    "Updated By": "updated_by_name",
    "Updated By Email": "updated_by_email",
    "Updated At": "updated_at",
    "Created At": "created_at"
  },
  "Fleet": {
    "Plate #": "plate_number",
    "Truck Type": "truck_type_name",
    "Vendor": "vendor_name",
    "Driver Name": "driver_name",
    "Driver Phone": "driver_phone",
    "Helper Name": "helper_name",
    "Status": "status",
    "Capacity": "capacity",
    "Is Active": "is_active",
    "Current Requests": "active_requests",
    "History Count": "history_count",
    "Created At": "created_at"
  },
  "Rate Management": {
    "Vendor": "vendor_name",
    "Truck Type": "truck_type_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Rate/Trip": "rate_per_trip",
    "Default Rate": "default_rate",
    "Effective Date": "effective_date",
    "Expiry Date": "expiry_date",
    "Is Active": "is_active",
    "Created At": "created_at"
  },
  "Vendor Speed Performance": {
    "Request #": "request_number",
    "Trip ID": "trip_id",
    "Drop #": "drop_sequence",
    "Distance (KM)": "distance_km",
    "Account": "account_name",
    "Department": "department_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Truck Type": "truck_type_name",
    "Vendor": "vendor_name",
    "Booking Date": "booking_date",
    "Status": "status_name",
    "Customs to Arrival": "lt_customs_to_arrival",
    "Pickup to Arrival": "lt_pickup_to_arrival",
    "Arrival to Start Load": "lt_arrival_to_start_load",
    "Start to End Load": "lt_start_load_to_end_load",
    "End Load to Arrived Dest": "lt_end_load_to_arrived_dest",
    "Arrived to Start Unload": "lt_arrived_dest_to_start_unload",
    "Start to End Unload": "lt_start_unload_to_end_unload",
    "Full Leg": "lt_full_leg"
  },
  "Cost Analysis": {
    "Request #": "request_number",
    "Trip ID": "trip_id",
    "Distance (KM)": "distance_km",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Truck Type": "truck_type_name",
    "Vendor": "vendor_name",
    "Plate #": "plate_number",
    "Booking Date": "booking_date",
    "Pickup": "pickup_datetime",
    "Est. Cost": "estimated_cost",
    "Actual Cost": "actual_cost",
    "Status": "status_name",
    "Foul Trip Reason": "foul_trip_reason"
  },
  "Ports":    { "ID": "id", "Name": "name", "Code": "code", "Address": "location", "Latitude": "latitude", "Longitude": "longitude", "Is Active": "is_active" },
  "Accounts": { "ID": "id", "Name": "name", "Code": "code", "Is Active": "is_active" },
  "Departments": { "ID": "id", "Name": "name", "Code": "code", "Is Active": "is_active" },
  "Packaging":   { "ID": "id", "Name": "name", "Code": "code", "Is Active": "is_active" },
  "Statuses":    { "ID": "id", "Name": "name", "Color": "color", "Is Active": "is_active" },
  "Truck Types": { "ID": "id", "Name": "name", "Code": "code", "Max KG": "max_capacity_kg", "Max CBM": "max_capacity_cbm", "Capacities": "capacities", "Is Active": "is_active" },
  "Vendors":     { "ID": "id", "Name": "name", "Contact Person": "contact_person", "Phone": "phone", "Email": "email", "Address": "address", "Is Active": "is_active" }
};

// ============================================================
// SETUP — run once
// ============================================================

function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var def = ss.getSheetByName("Sheet1");
  SECTIONS.forEach(function(s) {
    var sh = ss.getSheetByName(s.sheet);
    if (!sh) {
      sh = ss.insertSheet(s.sheet);
    }
    var hdrs = HEADERS[s.sheet] || [];
    if (hdrs.length) {
      sh.getRange(1, 1, 1, hdrs.length).setValues([hdrs]).setFontWeight("bold");
      sh.getFrozenRows() === 0 && sh.setFrozenRows(1);
    }
  });
  if (def && def.getLastRow() === 0 && def.getLastColumn() === 0) {
    ss.deleteSheet(def);
  }
  Logger.log("Sheets setup complete.");
}

// ============================================================
// AUTO-SYNC — called by time trigger (hourly)
// ============================================================

function syncAll() {
  SECTIONS.forEach(function(s) {
    try {
      syncSection(s);
    } catch (e) {
      Logger.log("ERROR syncing " + s.sheet + ": " + e);
    }
  });
  Logger.log("Sync complete at " + new Date().toISOString());
}

function syncSection(section) {
  var url = BACKEND_URL + section.endpoint;
  var options = { "method": "get", "muteHttpExceptions": true, "followRedirects": true };
  var resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() !== 200) {
    Logger.log("HTTP " + resp.getResponseCode() + " for " + section.endpoint);
    return;
  }
  var data = JSON.parse(resp.getContentText());
  if (!Array.isArray(data) || data.length === 0) {
    Logger.log(section.sheet + ": no data");
    return;
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(section.sheet);
  if (!sh) {
    sh = ss.insertSheet(section.sheet);
  }

  var hdrs = HEADERS[section.sheet] || [];
  var nested = NESTED_FIELDS[section.sheet] || {};

  var rows = data.map(function(row) {
    return hdrs.map(function(h) {
      var key = nested[h] || h.toLowerCase().replace(/ /g, "_");
      var val = row[key];
      if (val === undefined || val === null) return "";
      if (h === "Attachments" && Array.isArray(val)) {
        return val.map(function(a) { return a.original_filename || a.filename || a.name || ""; }).join(", ");
      }
      if (h === "Current Requests" && Array.isArray(val)) {
        return val.map(function(r) { return r.request_number || ""; }).join(", ");
      }
      if (h === "Capacities" && Array.isArray(val)) {
        return val.map(function(c) { return (c.packaging_type_name || "") + ": " + (c.max_quantity || 0); }).join("; ");
      }
      return String(val);
    });
  });

  if (sh.getLastRow() === 0 || sh.getRange(1, 1).getValue() === "") {
    if (hdrs.length) {
      sh.getRange(1, 1, 1, hdrs.length).setValues([hdrs]).setFontWeight("bold");
      sh.setFrozenRows(1);
    }
  }

  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).clearContent();
  }

  if (rows.length > 0 && hdrs.length) {
    sh.getRange(2, 1, rows.length, hdrs.length).setValues(rows);
  }

  Logger.log(section.sheet + ": synced " + rows.length + " rows");
}

// ============================================================
// TRIGGER MANAGEMENT
// ============================================================

function installTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger("syncAll")
    .timeBased()
    .everyHours(1)
    .create();
  Logger.log("Hourly auto-sync trigger installed.");
}

function removeTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });
  Logger.log("Auto-sync trigger removed.");
}

// ============================================================
// MANUAL SYNC — run from editor to test
// ============================================================

function manualSync() {
  syncAll();
}

function testConnection() {
  try {
    var resp = UrlFetchApp.fetch(BACKEND_URL + "/health", { "muteHttpExceptions": true });
    Logger.log("Health: " + resp.getResponseCode() + " " + resp.getContentText());
  } catch (e) {
    Logger.log("Connection failed: " + e);
  }
}
