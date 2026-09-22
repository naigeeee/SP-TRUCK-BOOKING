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

// Section → sheet tab name mapping
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

// Column headers for each sheet (order matters — matches API JSON keys)
var HEADERS = {
  "Masterlist": [
    "Request Number","Requestor Name","Requestor Email","Account","Department",
    "Origin Port","Destination Port","Truck Type","Packaging Type","Status",
    "Booking Date","Pickup Datetime","Arrived Dest Datetime","End Unloading Datetime",
    "Drop Sequence","Estimated Cost","Actual Cost","Helper Name",
    "Trip ID","Vendor Name","Plate Number","Distance (KM)","Attachments","Notes",
    "Delivery Remarks","Created At","Updated At"
  ],
  "Fleet": [
    "ID","Plate Number","Truck Type","Vendor","Status","Capacity",
    "Driver Name","Driver Phone","Is Active","Active Requests","Created At"
  ],
  "Rate Management": [
    "ID","Vendor","Truck Type","Origin Port","Destination Port",
    "Rate Per Trip","Default Rate","Effective Date","Is Active","Created At"
  ],
  "Vendor Speed Performance": [
    "ID","Request Number","Requestor Name","Requestor Email",
    "Pickup Datetime","Arrived Dest Datetime","End Unloading Datetime",
    "Status","Vendor Name","Plate Number","Origin Port","Destination Port",
    "Drop #","Distance (KM)","Lead Time Days"
  ],
  "Cost Analysis": [
    "ID","Request Number","Trip ID","Distance (KM)","Status","Origin Port","Destination Port",
    "Vendor Name","Plate Number","Estimated Cost","Actual Cost",
    "Booking Date","Created At"
  ],
  "Ports":        ["ID","Code","Name","Is Active","Created At"],
  "Accounts":     ["ID","Code","Name","Is Active","Created At"],
  "Departments":  ["ID","Code","Name","Is Active","Created At"],
  "Packaging":    ["ID","Code","Name","Is Active","Created At"],
  "Statuses":     ["ID","Name","Color","Is Active","Created At"],
  "Truck Types":  ["ID","Code","Name","Is Active","Created At","Capacities"],
  "Vendors":      ["ID","Code","Name","Contact Person","Phone","Is Active","Created At"]
};

// Key fields to extract from nested objects for master library lookups
var NESTED_FIELDS = {
  "Masterlist": {
    "Account": "account_name",
    "Department": "department_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Status": "status_name",
    "Truck Type": "truck_type_name",
    "Packaging Type": "packaging_type_name",
    "Vendor Name": "vendor_name",
    "Trip ID": "trip_id",
    "Plate Number": "plate_number",
    "Estimated Cost": "estimated_cost",
    "Actual Cost": "actual_cost",
    "Helper Name": "helper_name",
    "Drop Sequence": "drop_sequence",
    "Distance (KM)": "distance_km",
    "Attachments": "attachments",
    "Notes": "notes",
    "Delivery Remarks": "delivery_remarks"
  },
  "Fleet": {
    "Truck Type": "truck_type_name",
    "Vendor": "vendor_name",
    "Status": "status",
    "Capacity": "capacity",
    "Driver Name": "driver_name",
    "Driver Phone": "driver_phone",
    "Is Active": "is_active",
    "Active Requests": "active_requests"
  },
  "Rate Management": {
    "Vendor": "vendor_name",
    "Truck Type": "truck_type_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Rate Per Trip": "rate_per_trip",
    "Default Rate": "default_rate",
    "Effective Date": "effective_date",
    "Is Active": "is_active"
  },
  "Vendor Speed Performance": {
    "Status": "status_name",
    "Vendor Name": "vendor_name",
    "Plate Number": "plate_number",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Drop #": "drop_sequence",
    "Distance (KM)": "distance_km",
    "Lead Time Days": "lead_time_days"
  },
  "Cost Analysis": {
    "Status": "status_name",
    "Origin Port": "origin_port_name",
    "Destination Port": "destination_port_name",
    "Vendor Name": "vendor_name",
    "Plate Number": "plate_number",
    "Estimated Cost": "estimated_cost",
    "Actual Cost": "actual_cost",
    "Distance (KM)": "distance_km",
    "Trip ID": "trip_id"
  },
  "Ports":    { "Code": "code", "Name": "name", "Is Active": "is_active" },
  "Accounts": { "Code": "code", "Name": "name", "Is Active": "is_active" },
  "Departments": { "Code": "code", "Name": "name", "Is Active": "is_active" },
  "Packaging":   { "Code": "code", "Name": "name", "Is Active": "is_active" },
  "Statuses":    { "Name": "name", "Color": "color", "Is Active": "is_active" },
  "Truck Types": { "Code": "code", "Name": "name", "Is Active": "is_active", "Capacities": "capacities" },
  "Vendors":     { "Code": "code", "Name": "name", "Contact Person": "contact_person", "Phone": "phone", "Is Active": "is_active" }
};

// ============================================================
// SETUP — run once
// ============================================================

function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  // Remove default Sheet1 if empty
  var def = ss.getSheetByName("Sheet1");
  SECTIONS.forEach(function(s) {
    var sh = ss.getSheetByName(s.sheet);
    if (!sh) {
      sh = ss.insertSheet(s.sheet);
    }
    // Write headers
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

  // Build rows
  var rows = data.map(function(row) {
    return hdrs.map(function(h) {
      var key = nested[h] || h.toLowerCase().replace(/ /g, "_");
      var val = row[key];
      if (val === undefined || val === null) return "";
      if (h === "Attachments" && Array.isArray(val)) {
        return val.map(function(a) { return a.filename || a.name || ""; }).join(", ");
      }
      if (h === "Capacities" && Array.isArray(val)) {
        return val.map(function(c) { return (c.packaging_type_name || "") + ": " + (c.capacity || 0); }).join("; ");
      }
      return String(val);
    });
  });

  // Write headers if missing or blank
  if (sh.getLastRow() === 0 || sh.getRange(1, 1).getValue() === "") {
    if (hdrs.length) {
      sh.getRange(1, 1, 1, hdrs.length).setValues([hdrs]).setFontWeight("bold");
      sh.setFrozenRows(1);
    }
  }

  // Clear existing data (keep header row)
  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).clearContent();
  }

  // Write new data
  if (rows.length > 0 && hdrs.length) {
    sh.getRange(2, 1, rows.length, hdrs.length).setValues(rows);
  }

  Logger.log(section.sheet + ": synced " + rows.length + " rows");
}

// ============================================================
// TRIGGER MANAGEMENT
// ============================================================

function installTrigger() {
  // Remove existing triggers first
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });
  // Create hourly trigger
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
