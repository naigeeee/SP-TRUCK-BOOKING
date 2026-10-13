// ============================================================
// SP PH Truck Booking — Google Sheets Auto-Sync
// ============================================================
// SETUP:
// 1. Open Google Sheets → Extensions → Apps Script
// 2. Paste this entire script into Code.gs (replace what is there)
// 3. Set BACKEND_URL below to your deployed backend URL
// 4. Run setupSheets() once to create all tabs (re-run it after updating this
//    script to add the new tabs: Foul Trip Approval, Trip Utilisation Review and
//    Capacity Conversion)
// 5. Run installTrigger() once to enable hourly auto-sync
//
// Each tab mirrors the matching page in the app: the backend /api/sync/* endpoints
// return the same rows the page shows, and the column headers below follow the
// page's table. Headers are refreshed automatically on every sync.
// ============================================================

var BACKEND_URL = "https://sp-truck-booking--dev.ninjavan.apps.substrait.build";

var SECTIONS = [
  { key: "masterlist",          sheet: "Masterlist",               endpoint: "/api/sync/masterlist" },
  { key: "fleet",               sheet: "Fleet",                    endpoint: "/api/sync/fleet" },
  { key: "rates",               sheet: "Rate Management",          endpoint: "/api/sync/rates" },
  { key: "evaluation",          sheet: "Vendor Speed Performance", endpoint: "/api/sync/evaluation" },
  { key: "cost",                sheet: "Cost Analysis",            endpoint: "/api/sync/cost" },
  { key: "foul-trips",          sheet: "Foul Trip Approval",       endpoint: "/api/sync/foul-trips" },
  { key: "trip-utilisation",    sheet: "Trip Utilisation Review",  endpoint: "/api/sync/trip-utilisation" },
  { key: "ports",               sheet: "Ports",                    endpoint: "/api/sync/ports" },
  { key: "accounts",            sheet: "Accounts",                 endpoint: "/api/sync/accounts" },
  { key: "departments",         sheet: "Departments",              endpoint: "/api/sync/departments" },
  { key: "packaging",           sheet: "Packaging",                endpoint: "/api/sync/packaging" },
  { key: "statuses",            sheet: "Statuses",                 endpoint: "/api/sync/statuses" },
  { key: "truck-types",         sheet: "Truck Types",              endpoint: "/api/sync/truck-types" },
  { key: "vendors",             sheet: "Vendors",                  endpoint: "/api/sync/vendors" },
  { key: "capacity-conversion", sheet: "Capacity Conversion",      endpoint: "/api/sync/capacity-conversion" }
];

// Column header -> field name in the /api/sync/* response, per tab (order = column order).
var FIELDS = {
  "Masterlist": [
    ["Request #", "request_number"],
    ["Requestor Name", "requestor_name"],
    ["Requestor Email", "requestor_email"],
    ["Manifest", "manifest_status"],
    ["Status", "status_name"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Packaging", "packaging_type_name"],
    ["Initial Qty", "initial_qty"],
    ["Revised Qty", "revised_qty_out"],
    ["Vendor", "vendor_name"],
    ["Final Call Datetime", "final_call_datetime"],
    ["Trip ID", "trip_id"],
    ["Driver", "driver_username"],
    ["Driver Name", "driver_name"],
    ["Driver Phone", "driver_phone"],
    ["Drop #", "drop_sequence"],
    ["Distance (KM)", "distance_km"],
    ["Booking Date", "booking_date"],
    ["Initial Call datetime (TBC)", "call_datetime"],
    ["Customs Cleared", "customs_cleared_datetime"],
    ["Instructions", "special_instructions"],
    ["Arrived Pickup", "arrived_pickup_datetime"],
    ["Late Reason", "late_reason"],
    ["Start Loading", "start_loading_datetime"],
    ["End Loading", "end_loading_datetime"],
    ["Arrived Destination", "arrived_dest_datetime"],
    ["Start Unloading", "start_unloading_datetime"],
    ["End Unloading", "end_unloading_datetime"],
    ["Delivered Date", "delivered_date"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Foul Trip Date", "foul_trip_date"],
    ["Foul Trip Count Confirmation", "foul_trip_count"],
    ["Foul Trip Approval", "foul_trip_approved"],
    ["Cancellation Date", "cancellation_date"],
    ["Consol", "consolidated"],
    ["Est. Cost", "estimated_cost"],
    ["Actual Cost", "actual_cost"],
    ["Attachments", "attachments"],
    ["Updated By", "updated_by_name"],
    ["Updated By Email", "updated_by_email"],
    ["Updated At", "updated_at"],
    ["Created At", "created_at"]
  ],
  "Fleet": [
    ["Plate #", "plate_number"],
    ["Truck Type", "truck_type_name"],
    ["Vendor", "vendor_name"],
    ["Driver Name", "driver_name"],
    ["Driver Phone", "driver_phone"],
    ["Helper Name", "helper_name"],
    ["Status", "status"],
    ["Capacity", "capacity"],
    ["Is Active", "is_active"],
    ["Current Requests", "active_requests"],
    ["History Count", "history_count"],
    ["Created At", "created_at"]
  ],
  "Rate Management": [
    ["Vendor", "vendor_name"],
    ["Truck Type", "truck_type_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["Rate/Trip", "rate_per_trip"],
    ["Default Rate", "default_rate"],
    ["Additional Destination Drops", "additional_drops"],
    ["Foul Trip %", "foul_trip_pct"],
    ["Fuel Surcharge %", "fuel_surcharge_pct"],
    ["Effective Date", "effective_date"],
    ["Expiry Date", "expiry_date"],
    ["Is Active", "is_active"],
    ["Created At", "created_at"]
  ],
  "Vendor Speed Performance": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Drop #", "drop_sequence"],
    ["Distance (KM)", "distance_km"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date"],
    ["Status", "status_name"],
    ["Final Call Datetime", "final_call_datetime"],
    ["Delivered Date", "delivered_date"],
    ["Customs to Arrival", "lt_customs_to_arrival"],
    ["Initial Call datetime (TBC) to Arrival", "lt_pickup_to_arrival"],
    ["Arrival to Start Load", "lt_arrival_to_start_load"],
    ["Start to End Load", "lt_start_load_to_end_load"],
    ["End Load to Arrived Dest", "lt_end_load_to_arrived_dest"],
    ["Arrived to Start Unload", "lt_arrived_dest_to_start_unload"],
    ["Start to End Unload", "lt_start_unload_to_end_unload"],
    ["Full Leg", "lt_full_leg"]
  ],
  "Cost Analysis": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Distance (KM)", "distance_km"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date"],
    ["Initial Call datetime (TBC)", "call_datetime"],
    ["Final Call Datetime", "final_call_datetime"],
    ["Delivered Date", "delivered_date"],
    ["Rate Basis", "rate_basis"],
    ["Rate Amount", "rate_amount"],
    ["Actual Cost", "actual_cost"],
    ["Toll Fee", "toll_fee"],
    ["Management Fee", "management_fee"],
    ["Fuel", "fuel"],
    ["Parking", "parking"],
    ["Miscellaneous", "miscellaneous"],
    ["Manpower", "manpower"],
    ["Toll", "toll"],
    ["Welfare", "welfare"],
    ["WH Rental", "wh_rental"],
    ["Toll Fee (Easytrip)", "toll_fee_easytrip"],
    ["Toll Fee (Autosweep)", "toll_fee_autosweep"],
    ["Foul Trip Cost", "foul_trip_cost"],
    ["Fuel Surcharge Cost", "fuel_surcharge_cost"],
    ["Total Cost", "total_cost"],
    ["Status", "status_name"],
    ["Foul Trip Date", "foul_trip_date"],
    ["Foul Trip Count Confirmation", "foul_trip_count"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Updated By", "cost_updated_by_email"],
    ["Updated At", "cost_updated_at"]
  ],
  "Foul Trip Approval": [
    ["Request #", "request_number"],
    ["Trip ID", "trip_id"],
    ["Account", "account_name"],
    ["Department", "department_name"],
    ["Distance (KM)", "distance_km"],
    ["Origin Port", "origin_port_name"],
    ["Destination Port", "destination_port_name"],
    ["International MAWB", "international_mawb"],
    ["Domestic MAWB", "domestic_mawb"],
    ["Truck Type", "truck_type_name"],
    ["Truck Plate #", "plate_number"],
    ["Vendor", "vendor_name"],
    ["Booking Date", "booking_date"],
    ["Initial Call datetime (TBC)", "call_datetime"],
    ["Final Call Datetime", "final_call_datetime"],
    ["Rate Basis", "rate_basis"],
    ["Rate/Trip", "rate_per_trip"],
    ["Foul Trip %", "foul_trip_pct"],
    ["Foul Trip Date", "foul_trip_date"],
    ["Foul Trip Count Confirmation", "foul_trip_count"],
    ["Foul Trip Cost", "foul_trip_cost"],
    ["Foul Trip Reason", "foul_trip_reason"],
    ["Status", "status_name"],
    ["Approval Status", "approval_status"],
    ["Approved By", "foul_trip_approved_by_email"],
    ["Approved At", "foul_trip_approved_at"]
  ],
  "Trip Utilisation Review": [
    ["Trip ID", "trip_id"],
    ["Final Call Datetime", "final_call_datetime"],
    ["Status", "status_name"],
    ["Requests", "request_count"],
    ["Origin Port", "origin_port_name"],
    ["Department", "department_name"],
    ["Vendor", "vendor_name"],
    ["Truck Type", "truck_type_name"],
    ["Capacity (units)", "max_capacity_units"],
    ["Initial Qty (units)", "initial_units"],
    ["Initial Utilisation %", "initial_utilisation"],
    ["Initial Tier", "initial_tier"],
    ["Revised Qty (units)", "revised_units"],
    ["Revised Utilisation %", "revised_utilisation"],
    ["Revised Tier", "revised_tier"]
  ],
  "Ports":        [["ID", "id"], ["Name", "name"], ["Code", "code"], ["Address", "location"], ["Latitude", "latitude"], ["Longitude", "longitude"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Accounts":     [["ID", "id"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Departments":  [["ID", "id"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Packaging":    [["ID", "id"], ["Name", "name"], ["Code", "code"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Statuses":     [["ID", "id"], ["Name", "name"], ["Color", "color"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Truck Types":  [["ID", "id"], ["Name", "name"], ["Code", "code"], ["Max KG", "max_capacity_kg"], ["Max CBM", "max_capacity_cbm"], ["Max Capacity (units)", "max_capacity_units"], ["Capacities", "capacities"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Vendors":      [["ID", "id"], ["Name", "name"], ["Contact Person", "contact_person"], ["Phone", "phone"], ["Email", "email"], ["Address", "address"], ["Is Active", "is_active"], ["Created At", "created_at"]],
  "Capacity Conversion": [
    ["Packaging Type", "packaging_type"],
    ["Code", "code"],
    ["Base Packaging Unit", "base_unit"],
    ["Is Base Unit", "is_base"],
    ["Factor (base units per 1 unit)", "factor"],
    ["Inverse", "inverse"]
  ]
};

function headersFor(sheetName) {
  return (FIELDS[sheetName] || []).map(function(f) { return f[0]; });
}

// ============================================================
// SETUP — run once (and again after updating this script)
// ============================================================

function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var def = ss.getSheetByName("Sheet1");
  SECTIONS.forEach(function(s) {
    var sh = ss.getSheetByName(s.sheet);
    if (!sh) {
      sh = ss.insertSheet(s.sheet);
    }
    var hdrs = headersFor(s.sheet);
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

function cellValue(header, val) {
  if (val === undefined || val === null) return "";
  if (header === "Attachments" && Array.isArray(val)) {
    return val.map(function(a) {
      var name = a.original_filename || a.filename || a.name || "";
      return a.download_url ? name + " (" + BACKEND_URL + a.download_url + ")" : name;
    }).join(", ");
  }
  if (header === "Current Requests" && Array.isArray(val)) {
    return val.map(function(r) { return r.request_number || ""; }).join(", ");
  }
  if (header === "Capacities" && Array.isArray(val)) {
    return val.map(function(c) { return (c.packaging_type_name || "") + ": " + (c.max_quantity || 0); }).join("; ");
  }
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (Array.isArray(val)) return val.map(function(x) { return typeof x === "object" ? JSON.stringify(x) : String(x); }).join(", ");
  if (typeof val === "object") return JSON.stringify(val);
  if (typeof val === "number") return val;
  return String(val);
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
  if (!Array.isArray(data)) data = [];

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(section.sheet);
  if (!sh) {
    sh = ss.insertSheet(section.sheet);
  }

  var fields = FIELDS[section.sheet] || [];
  var hdrs = headersFor(section.sheet);

  // Keep the header row in line with this script (new / renamed columns).
  if (hdrs.length) {
    var lastCol = Math.max(sh.getLastColumn(), hdrs.length);
    var curHdr = sh.getLastRow() > 0 ? sh.getRange(1, 1, 1, lastCol).getValues()[0] : [];
    var needsUpdate = sh.getLastColumn() > hdrs.length;
    for (var hi = 0; !needsUpdate && hi < hdrs.length; hi++) {
      if (String(curHdr[hi] || "") !== hdrs[hi]) needsUpdate = true;
    }
    if (needsUpdate) {
      if (sh.getLastColumn() > hdrs.length) {
        sh.getRange(1, hdrs.length + 1, Math.max(sh.getLastRow(), 1), sh.getLastColumn() - hdrs.length).clearContent();
      }
      sh.getRange(1, 1, 1, hdrs.length).setValues([hdrs]).setFontWeight("bold");
      if (sh.getFrozenRows() === 0) sh.setFrozenRows(1);
      Logger.log(section.sheet + ": headers refreshed");
    }
  }

  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, Math.max(sh.getLastColumn(), 1)).clearContent();
  }

  if (!data.length) {
    Logger.log(section.sheet + ": cleared (no data)");
    return;
  }

  var rows = data.map(function(row) {
    return fields.map(function(f) { return cellValue(f[0], row[f[1]]); });
  });

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
