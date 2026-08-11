import { useEffect, useState, useCallback } from "react";
import "@cloudscape-design/global-styles/index.css";
import { Box, Button, SpaceBetween, Table } from "@cloudscape-design/components";
import Header from "@cloudscape-design/components/header";
import { Storage, Auth } from "aws-amplify";

// ✅ Define table columns
const columnDefinitions = [
  {
    id: "key",
    cell: (item) => item.key,
    header: "Filename",
  },
  {
    id: "size",
    header: "Size",
    cell: (item) => (item.size / 1024 / 1024).toFixed(2) + " MB",
    minWidth: 10,
  },
  {
    id: "lastModified",
    header: "Last Modified",
    cell: (item) => item.lastModified.toString(),
  },
];

// 🔍 Step 1 — AI anomaly detector function (uses your actual API endpoint)
async function checkAnomaly(userId) {
  try {
    const response = await fetch(
      "https://spqyfzfol3.execute-api.ap-south-1.amazonaws.com/prod/check", // ✅ your endpoint
      {
        method: "POST",
        mode: "cors",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      }
    );

    const data = await response.json();

    try {
      return JSON.parse(data.body);
    } catch {
      return data;
    }
  } catch (error) {
    console.error("❌ Error calling anomaly API:", error);
    return { status: "ERROR", error: error.message };
  }
}

function TableListFiles(props) {
  const [items, setItems] = useState([]);
  const [selectedItems, setSelectedItems] = useState([]);

  // ✅ Wrap `load` in useCallback (so React doesn’t warn)
  const load = useCallback(async () => {
    try {
      const result = await Storage.list("", { level: props.level });
      setItems(result.results);
    } catch (err) {
      console.log(err);
    }
  }, [props.level]);

  useEffect(() => {
    load();
  }, [load]);

  // 🧱 Step 2 — Handle download + OTP verification
  async function handleDownload(filename) {
    try {
      const user = await Auth.currentAuthenticatedUser();
      const userId = user.username;

      console.log("🔍 Checking anomaly for:", userId);
      const result = await checkAnomaly(userId);
      console.log("AI result:", result);

      // 🚨 Suspicious activity → trigger Cognito OTP flow
      if (result.status === "OTP_REQUIRED") {
        alert("⚠️ Suspicious activity detected! Sending verification code...");

        try {
          // 🔹 Step 1: Cognito sends verification code to user's email
          await Auth.verifyCurrentUserAttribute("email");

          // 🔹 Step 2: Ask user to enter the OTP
          const code = prompt("Enter the OTP sent to your email:");

          if (code) {
            // 🔹 Step 3: Verify entered OTP with Cognito
            await Auth.verifyCurrentUserAttributeSubmit("email", code);
            alert("✅ OTP verified successfully! Starting download...");
            downloadFile(filename);
          } else {
            alert("❌ No OTP entered. Download cancelled.");
          }
        } catch (otpErr) {
          console.error("OTP verification failed:", otpErr);
          alert("❌ OTP verification failed. Try again later.");
        }

        return; // Stop here if OTP_REQUIRED
      }

      // ✅ Normal behaviour — safe download
      if (result.status === "OK") {
        alert("✅ Verified! Safe to download.");
        downloadFile(filename);
      } else {
        alert("❌ Error checking AI service: " + (result.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Download failed:", error);
    }
  }

  function downloadFile(filename) {
    Storage.get(filename, { level: props.level })
      .then((result) => openInNewTab(result))
      .catch((err) => console.error("Download error:", err));
  }

  function deleteFile(filename) {
    Storage.remove(filename, { level: props.level })
      .then(() => load())
      .catch((error) => console.log(error));
  }

  const openInNewTab = (url) => {
    const newWindow = window.open(url, "_blank", "noopener,noreferrer");
    if (newWindow) newWindow.opener = null;
  };

  return (
    <Table
      items={items}
      columnDefinitions={columnDefinitions}
      onSelectionChange={({ detail }) => setSelectedItems(detail.selectedItems)}
      header={
        <Header
          actions={
            <SpaceBetween size="xs" direction="horizontal">
              <Button onClick={() => load()}>Refresh</Button>
              <Button
                disabled={selectedItems.length === 0}
                onClick={() => handleDownload(selectedItems[0].key)}
              >
                Download
              </Button>
              <Button
                disabled={selectedItems.length === 0}
                onClick={() => deleteFile(selectedItems[0].key)}
              >
                Delete
              </Button>
            </SpaceBetween>
          }
        ></Header>
      }
      selectionType="single"
      selectedItems={selectedItems}
      empty={
        <Box margin={{ vertical: "xs" }} textAlign="center" color="inherit">
          <SpaceBetween size="xxs">
            <div>
              <b>No files uploaded yet</b>
              <Box variant="p" color="inherit">
                You don't have any files uploaded yet.
              </Box>
            </div>
          </SpaceBetween>
        </Box>
      }
    />
  );
}

export default TableListFiles;
