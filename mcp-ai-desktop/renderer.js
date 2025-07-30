// renderer.js
import {marked} from "./node_modules/marked/lib/marked.esm.js";
import katex from "./node_modules/katex/dist/katex.mjs";

document.addEventListener("DOMContentLoaded", async () => {
  const messageInput = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const chatMessages = document.getElementById("chat-messages");
  const addServerBtn = document.getElementById("add-server-btn");
  const serverList = document.getElementById("server-list");
  const settingsBtn = document.getElementById("settings-btn");

  // Image upload elements
  const imageBtn = document.getElementById("image-btn");
  const imageInput = document.getElementById("image-input");
  const imagePreviewContainer = document.getElementById("image-preview-container");
  const previewImage = document.getElementById("preview-image");
  const removeImageBtn = document.getElementById("remove-image-btn");

  // Settings panel elements
  const settingsPanel = document.getElementById("settings-panel");
  const settingsOverlay = document.getElementById("settings-overlay");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const settingsBackendSelect = document.getElementById("settings-backend-select");
  const settingsApiKey = document.getElementById("settings-api-key");
  const settingsModelSelect = document.getElementById("settings-model-select");
  const settingsSaveBtn = document.getElementById("settings-save-btn");
  const settingsCancelBtn = document.getElementById("settings-cancel-btn");

  let pythonPort = null;
  let serverRefreshInterval = null;
  let selectedImageData = null; // Store the selected image data

  function renderLaTeX(text) {
    const latexPlaceholders = [];
    let placeholderIndex = 0;

    function replaceAndRender(match, displayMode) {
      const latex = match.slice(displayMode ? 2 : 1, -(displayMode ? 2 : 1));
      try {
        const rendered = katex.renderToString(latex, {
          throwOnError: false,
          displayMode: displayMode,
          output: "html",
        });
        const placeholder = `__LATEX_PLACEHOLDER_${placeholderIndex++}__`;
        latexPlaceholders.push({placeholder, rendered});
        return placeholder;
      } catch (e) {
        console.error("KaTeX rendering error:", e);
        return match; // Return original on error
      }
    }

    let processedText = text.replace(/\$\$([\s\S]*?)\$\$/g, (match) =>
      replaceAndRender(match, true)
    );
    processedText = processedText.replace(
      /(?<!\$)\$([^$]+)\$(?!\$)/g,
      (match) => replaceAndRender(match, false)
    );

    return {processedText, latexPlaceholders};
  }

  // Returns the created messageDiv element
  function addMessage(text, sender) {
      const messageDiv = document.createElement("div");
      // Add base 'message' class and specific sender class
      messageDiv.classList.add("message", sender);

      const toolCallPatterns = [
          /need to make a call to the .* function/i,
          /using the .* tool/i,
          /calling the .* function/i,
          /let me use the .* tool/i,
          /i need to use the .* tool/i,
          /to get .* i need to make a call to the .* function/i,
      ];

      // --- Tool Status Message Handling ---
      let isToolStatusMessage = false;
      let toolStatusType = ''; // 'start' or 'end'
      let toolStatusDetails = '';
      if (typeof text === 'string') {
          if (text.startsWith("TOOL_CALL_START:")) {
              isToolStatusMessage = true;
              toolStatusType = 'start';
              toolStatusDetails = text.substring("TOOL_CALL_START:".length).trim();
              // Ensure correct classes are set
              messageDiv.classList.remove('ai', 'user', 'system'); // Remove others if present
              messageDiv.classList.add("system", "tool-status");
              sender = "system tool-status"; // Update sender variable for logic below
          } else if (text.startsWith("TOOL_CALL_END:")) {
              isToolStatusMessage = true;
              toolStatusType = 'end';
              toolStatusDetails = text.substring("TOOL_CALL_END:".length).trim();
              // Ensure correct classes are set
              messageDiv.classList.remove('ai', 'user', 'system'); // Remove others if present
              messageDiv.classList.add("system", "tool-status");
              sender = "system tool-status"; // Update sender variable for logic below
          }
      }
      // --- End Tool Status Message Handling ---

      const isToolCallAnnouncement = // Keep original pattern matching for now
          sender === "ai" && toolCallPatterns.some((pattern) => pattern.test(text));
      const isSystemMessage = sender.startsWith("system"); // Includes "system", "system error", "system tool-status"

      // Use collapsible details for system messages AND tool status messages
      if (isSystemMessage) { // Simplified check now includes tool status
          const details = document.createElement("details");
          details.classList.add("message-details");
          if (isToolStatusMessage) details.open = true; // Open tool status by default

          const summary = document.createElement("summary");
          summary.classList.add("message-summary");

          // Set summary text based on type
          if (isToolStatusMessage) {
              const toolName = toolStatusDetails.split(' ')[0] || 'Unknown Tool';
              if (toolStatusType === 'start') {
                  summary.textContent = `Calling Tool: ${toolName}...`;
              } else { // 'end'
                  const statusPart = toolStatusDetails.split('status=')[1] || ''; // Get everything after 'status='
                  const isError = statusPart.toLowerCase().startsWith('error');
                  summary.textContent = `Tool Finished: ${toolName} (${isError ? 'Error' : 'Success'})`;
                  if (isError) summary.style.color = 'var(--status-error)'; // Style error summary
              }
          } else if (isToolCallAnnouncement) { // Keep this for now
              summary.textContent = "AI is using a tool...";
          } else { // Regular system message
              summary.textContent = text.startsWith("Error:") ? "System Error" : "System Message";
              if (text.startsWith("Error:")) summary.style.color = 'var(--status-error)';
          }

          const detailsContent = document.createElement("div");
          detailsContent.classList.add("message-details-content");
          // For tool status, only show the status part in details, not the full raw result
          if (isToolStatusMessage) {
              const statusPart = toolStatusDetails.split('status=')[1] || toolStatusDetails; // Fallback to full details if 'status=' not found
              detailsContent.textContent = statusPart.trim();
              detailsContent.style.overflowWrap = 'break-word'; // Ensure status text wraps
          } else {
             detailsContent.textContent = text; // Show full text for regular system messages
          }

          details.appendChild(summary);
          details.appendChild(detailsContent);
          messageDiv.appendChild(details);
      } else { // Regular user or AI message
          const contentDiv = document.createElement("div");
          contentDiv.classList.add("message-content");

          if (sender === "ai") {
              try {
                  const {processedText, latexPlaceholders} = renderLaTeX(text);
                  let html = marked.parse(processedText);
                  latexPlaceholders.forEach(({placeholder, rendered}) => {
                      html = html.replace(placeholder, rendered);
                  });
                  contentDiv.innerHTML = html;
              } catch (parseError) {
                  console.error("Error parsing AI message content:", parseError);
                  contentDiv.textContent = text; // Fallback to raw text on error
              }
          } else { // User message
              contentDiv.textContent = text;
          }
          messageDiv.appendChild(contentDiv);
      }

      chatMessages.appendChild(messageDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      return messageDiv; // Return the created element
  }

  // --- Helper Functions defined at the correct scope ---

  // Helper function to update content of an existing message div
  function updateMessageContent(messageDiv, text, senderClass) {
      // Clear existing content and classes related to sender/type
      messageDiv.innerHTML = '';
      messageDiv.className = 'message'; // Reset class list
      messageDiv.classList.add(senderClass); // Add new sender class

      // --- Tool Status Message Handling (Copied from addMessage) ---
      let isToolStatusMessage = false;
      let toolStatusType = '';
      let toolStatusDetails = '';
       if (typeof text === 'string') {
          if (text.startsWith("TOOL_CALL_START:")) {
              isToolStatusMessage = true;
              toolStatusType = 'start';
              toolStatusDetails = text.substring("TOOL_CALL_START:".length).trim();
              senderClass = "system tool-status"; // Ensure correct class
              messageDiv.classList.remove('ai', 'user', 'system', 'ai-loading');
              messageDiv.classList.add("system", "tool-status");
          } else if (text.startsWith("TOOL_CALL_END:")) {
              isToolStatusMessage = true;
              toolStatusType = 'end';
              toolStatusDetails = text.substring("TOOL_CALL_END:".length).trim();
              senderClass = "system tool-status"; // Ensure correct class
              messageDiv.classList.remove('ai', 'user', 'system', 'ai-loading'); // Use valid class name here too
              messageDiv.classList.add("system", "tool-status");
          }
      }
      // --- End Tool Status Message Handling ---

      // Re-apply rendering logic (similar to addMessage)
      const isSystemMessage = senderClass.startsWith("system");
      const isAiMessage = senderClass === "ai";

      // Use collapsible details for system messages AND tool status messages
      if (isSystemMessage) { // Includes tool status and errors
          const details = document.createElement("details");
          details.classList.add("message-details");
          if (isToolStatusMessage) details.open = true; // Open tool status by default

          const summary = document.createElement("summary");
          summary.classList.add("message-summary");

          if (isToolStatusMessage) {
              const toolName = toolStatusDetails.split(' ')[0] || 'Unknown Tool';
              if (toolStatusType === 'start') {
                  summary.textContent = `Calling Tool: ${toolName}...`;
              } else { // 'end'
                  const statusPart = toolStatusDetails.split('status=')[1] || ''; // Get everything after 'status='
                  const isError = statusPart.toLowerCase().startsWith('error');
                  summary.textContent = `Tool Finished: ${toolName} (${isError ? 'Error' : 'Success'})`;
                   if (isError) summary.style.color = 'var(--status-error)';
              }
          } else { // Regular system message or system error
              summary.textContent = text.startsWith("Error:") ? "System Error" : "System Message";
              if (senderClass === "system error" || text.startsWith("Error:")) {
                 summary.style.color = 'var(--status-error)';
              }
          }

          const detailsContent = document.createElement("div");
          detailsContent.classList.add("message-details-content");
          // For tool status, only show the status part in details
          if (isToolStatusMessage) {
              const statusPart = toolStatusDetails.split('status=')[1] || toolStatusDetails;
              detailsContent.textContent = statusPart.trim();
              detailsContent.style.overflowWrap = 'break-word'; // Ensure status text wraps
          } else {
             detailsContent.textContent = text; // Show full text for regular system messages
          }

          details.appendChild(summary);
          details.appendChild(detailsContent);
          messageDiv.appendChild(details);

      } else if (isAiMessage) {
          const contentDiv = document.createElement("div");
          contentDiv.classList.add("message-content");
           try {
              const {processedText, latexPlaceholders} = renderLaTeX(text);
              let html = marked.parse(processedText);
              latexPlaceholders.forEach(({placeholder, rendered}) => {
                html = html.replace(placeholder, rendered);
              });
              contentDiv.innerHTML = html;
            } catch (parseError) {
               console.error("Error parsing AI message content:", parseError);
               contentDiv.textContent = text; // Fallback to raw text on error
            }
          messageDiv.appendChild(contentDiv);
      } else { // Should primarily be 'user' or 'ai-loading'
           messageDiv.textContent = text; // Default to text for user or loading placeholder
      }
      chatMessages.scrollTop = chatMessages.scrollHeight; // Ensure scroll stays at bottom
  }


  // Helper function to handle potentially multi-line backend responses
  // containing status messages and the final AI reply.
  function handleBackendResponse(loadingMessageDiv, responseText) {
      const lines = responseText.split('\n');
      const statusMessages = [];
      const finalReplyLines = [];

      lines.forEach(line => {
          if (line.startsWith("TOOL_CALL_START:") || line.startsWith("TOOL_CALL_END:")) {
              statusMessages.push(line);
          } else if (line.trim().length > 0) { // Collect non-empty lines for final reply
              finalReplyLines.push(line);
          }
      });

      // Display status messages first as separate messages
      statusMessages.forEach(statusMsg => {
          addMessage(statusMsg, "system"); // Let addMessage handle parsing TOOL_CALL_*
      });

      // Update the original loading message with the final AI reply
      const finalReply = finalReplyLines.join('\n').trim();
      if (loadingMessageDiv) { // Check if loading message still exists
          if (finalReply) {
              updateMessageContent(loadingMessageDiv, finalReply, "ai");
          } else if (statusMessages.length > 0) {
              // If there were only status messages and no final reply text
              loadingMessageDiv.remove(); // Remove the original loading message
          } else {
              // If the response was completely empty or just whitespace
              updateMessageContent(loadingMessageDiv, "(Received empty response)", "system");
          }
      } else if (finalReply) {
          // If loading message was removed but we have a final reply, add it
          addMessage(finalReply, "ai");
      }
  }

  // --- Image Handling Functions ---

  function clearSelectedImage() {
    selectedImageData = null;
    imagePreviewContainer.style.display = 'none';
    previewImage.src = '';
    imageInput.value = ''; // Clear the file input
    // Ensure send button is visible and properly positioned after clearing image
    sendBtn.style.visibility = 'visible';
    sendBtn.style.zIndex = '10';
  }

  async function handleImageSelection(file) {
    if (!file || !file.type.startsWith('image/')) {
      addMessage("Please select a valid image file.", "system");
      return;
    }

    // Check file size (limit to 10MB)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      addMessage("Image file is too large. Please select an image smaller than 10MB.", "system");
      return;
    }

    try {
      // Show processing state
      imageBtn.classList.add('processing');
      imageBtn.title = 'Processing image...';

      // Create a temporary file path for preview
      const objectUrl = URL.createObjectURL(file);
      previewImage.src = objectUrl;
      imagePreviewContainer.style.display = 'block';

      // Ensure send button remains visible and properly positioned
      sendBtn.style.visibility = 'visible';
      sendBtn.style.zIndex = '10';

      // Convert to base64 for sending to backend
      const reader = new FileReader();
      reader.onload = function(e) {
        const base64Data = e.target.result.split(',')[1]; // Remove data:image/...;base64, prefix
        selectedImageData = {
          data: base64Data,
          mimeType: file.type,
          name: file.name
        };

        // Remove processing state
        imageBtn.classList.remove('processing');
        imageBtn.title = 'Add image';

        // Clean up object URL to prevent memory leaks
        URL.revokeObjectURL(objectUrl);
      };
      reader.onerror = function() {
        console.error("Error reading file");
        addMessage("Error reading image file. Please try again.", "system");
        clearSelectedImage();
        imageBtn.classList.remove('processing');
        imageBtn.title = 'Add image';
        URL.revokeObjectURL(objectUrl);
      };
      reader.readAsDataURL(file);

    } catch (error) {
      console.error("Error processing image:", error);
      addMessage("Error processing image. Please try again.", "system");
      clearSelectedImage();
      imageBtn.classList.remove('processing');
      imageBtn.title = 'Add image';
    }
  }

  function createImageMessage(imageData, text = '') {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", "user");

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");

    // Add image
    const img = document.createElement("img");
    img.classList.add("message-image");
    img.src = `data:${imageData.mimeType};base64,${imageData.data}`;
    img.alt = imageData.name || "Uploaded image";
    contentDiv.appendChild(img);

    // Add text if provided
    if (text.trim()) {
      const textDiv = document.createElement("div");
      textDiv.classList.add("message-text");
      textDiv.textContent = text;
      contentDiv.appendChild(textDiv);
    }

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
  }

  // --- End Image Handling Functions ---

  // --- End Helper Functions ---

  async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message && !selectedImageData) {
      return; // Don't send empty messages without image
    }

    if (!pythonPort) {
      addMessage("Error: Backend not connected.", "system");
      return;
    }

    // Create message data object
    const messageData = {
      text: message || "" // Ensure we always send a text field, even if empty
    };

    // Add image if selected
    if (selectedImageData) {
      messageData.image = selectedImageData;
      // Display the user message with image
      createImageMessage(selectedImageData, message);
      // Clear the selected image
      clearSelectedImage();

      // Add a helpful status message for image processing
      if (!message.trim()) {
        addMessage("Processing image...", "system");
      }
    } else {
      // Display regular text message
      addMessage(message, "user");
    }

    messageInput.value = "";
    messageInput.style.height = "auto"; // Reset height after sending

    // Add a temporary loading message for AI response
    const loadingMessageDiv = addMessage("...", "ai-loading");

    try {
      const response = await fetch(`http://127.0.0.1:${pythonPort}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({message: messageData}),
      });
      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({reply: `HTTP error! status: ${response.status}`}));
        throw new Error(
          errorData.reply || `HTTP error! status: ${response.status}`
        );
      }
      const data = await response.json();
      // Handle potential multi-line responses with status messages
      handleBackendResponse(loadingMessageDiv, data.reply);
    } catch (error) {
      console.error("Error sending message:", error);
      // Update loading message to show error
      if (loadingMessageDiv) { // Check if it exists before updating
        updateMessageContent(loadingMessageDiv, `Error: ${error.message}`, "system error");
      } else { // If loading message somehow got removed, add a new error message
        addMessage(`Error: ${error.message}`, "system error");
      }
    }
  }

  async function deleteServer(serverIdentifier) { // Use identifier
    if (!pythonPort) {
      addMessage("Cannot delete server: Backend not connected.", "system");
      return;
    }

    // Determine display name for message (might be path or name)
    const displayName = serverIdentifier.includes('/') || serverIdentifier.includes('\\')
      ? serverIdentifier.split(/[\\/]/).pop()
      : serverIdentifier;

    addMessage(
      `Attempting to remove server: ${displayName}`,
      "system"
    );
    try {
      const response = await fetch(`http://127.0.0.1:${pythonPort}/servers`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({identifier: serverIdentifier}), // Send identifier
      });
      const data = await response.json();
      if (response.ok && data.status === "success") {
        addMessage(
          `Server ${displayName} removed.`,
          "system"
        );
        await fetchAndRenderServers(); // Refresh the list
      } else {
        throw new Error(
          data.message || `Failed to remove server (status: ${response.status})`
        );
      }

      // Incorrectly nested helper functions removed from here.

    } catch (error) {
      console.error("Error removing server:", error);
      addMessage(`Error removing server: ${error.message}`, "system");
      await fetchAndRenderServers(); // Refresh list even on error
    }
  }

  function renderServerList(servers) {
    serverList.innerHTML = ""; // Clear existing list
    if (servers && servers.length > 0) {
      servers.forEach((server) => {
        const li = document.createElement("li");
        li.dataset.identifier = server.identifier; // Use identifier
        li.classList.add("server-item");

        const serverInfo = document.createElement("div");
        serverInfo.classList.add("server-info");

        const nameSpan = document.createElement("span");
        nameSpan.classList.add("server-name");
        nameSpan.textContent = server.display_name; // Use display_name
        nameSpan.title = server.identifier; // Show full identifier on hover

        const statusSpan = document.createElement("span");
        statusSpan.classList.add(
          "server-status",
          server.status === "connected" ? "connected" : "error"
        );
        statusSpan.textContent = server.status;

        const deleteBtn = document.createElement("button");
        deleteBtn.classList.add("delete-server-btn");
        deleteBtn.innerHTML = "×"; // Simple 'x'
        deleteBtn.title = "Remove Server";
        deleteBtn.onclick = () => deleteServer(server.identifier); // Pass identifier

        serverInfo.appendChild(nameSpan);
        serverInfo.appendChild(statusSpan);
        serverInfo.appendChild(deleteBtn);
        li.appendChild(serverInfo);

        if (server.tools && server.tools.length > 0) {
          const toolsContainer = document.createElement("div");
          toolsContainer.classList.add("tools-container");
          const toolsTitle = document.createElement("span");
          toolsTitle.classList.add("tools-title");
          toolsTitle.textContent = "Tools:";
          toolsContainer.appendChild(toolsTitle);

          const toolsList = document.createElement("ul");
          toolsList.classList.add("tools-list");
          server.tools.forEach((toolName) => {
            const toolLi = document.createElement("li");
            toolLi.textContent = toolName;
            toolsList.appendChild(toolLi);
          });
          toolsContainer.appendChild(toolsList);
          li.appendChild(toolsContainer);
        }

        serverList.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.textContent = "No MCP servers connected.";
      li.style.justifyContent = "center";
      li.style.color = "var(--text-secondary)";
      serverList.appendChild(li);
    }
  }

  async function fetchAndRenderServers() {
    if (!pythonPort) return;
    try {
      const response = await fetch(`http://127.0.0.1:${pythonPort}/servers`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      if (data.status === "success") {
        renderServerList(data.servers);
      } else {
        throw new Error(data.message || "Failed to fetch servers");
      }
    } catch (error) {
      console.error("Error fetching servers:", error);
      renderServerList([]);
      addMessage(`Error fetching server list: ${error.message}`, "system");
      if (serverRefreshInterval) {
        clearInterval(serverRefreshInterval);
        serverRefreshInterval = null;
        addMessage(
          "Stopping automatic server refresh due to connection error.",
          "system"
        );
      }
    }
  }

  async function initializeApp() {
    try {
      pythonPort = await window.electronAPI.getPythonPort();
      console.log(`Python backend running on port: ${pythonPort}`);
      addMessage("Ask me Anything!", "ai");
      addMessage("💡 You can now upload images by clicking the image button or dragging and dropping them into the chat!", "system");
      await fetchAndRenderServers();
      if (!serverRefreshInterval) {
        serverRefreshInterval = setInterval(fetchAndRenderServers, 10000);
      }
    } catch (error) {
      console.error("Error initializing app:", error);
      addMessage(
        "Error connecting to backend. Please ensure it is running.",
        "system"
      );
      renderServerList([]);
      if (serverRefreshInterval) {
        clearInterval(serverRefreshInterval);
        serverRefreshInterval = null;
      }
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  messageInput.addEventListener("keydown", (event) => {
    // Handle Enter key for sending messages
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }

    // Also handle Ctrl+Enter or Cmd+Enter for sending
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });

  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 150)}px`;
  });

  // Image upload event listeners
  imageBtn.addEventListener("click", () => {
    imageInput.click();
  });

  imageInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      handleImageSelection(file);
    }
  });

  removeImageBtn.addEventListener("click", () => {
    clearSelectedImage();
  });

  // Drag and drop support for images
  document.addEventListener("dragover", (event) => {
    event.preventDefault();
  });

  document.addEventListener("drop", (event) => {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0 && files[0].type.startsWith('image/')) {
      handleImageSelection(files[0]);
    }
  });

  addServerBtn.addEventListener("click", async () => {
    if (!pythonPort) {
      addMessage("Cannot add server: Backend not connected.", "system");
      return;
    }

    // Update dialog options to accept both .py and .json
    const dialogOptions = {
      properties: ["openFile"],
      filters: [
        { name: 'MCP Server Files', extensions: ['py', 'json'] },
        { name: 'Python Scripts', extensions: ['py'] },
        { name: 'JSON Config', extensions: ['json'] },
        { name: 'All Files', extensions: ['*'] }
      ]
    };

    const filePaths = await window.electronAPI.showOpenDialog(dialogOptions);

    if (filePaths && filePaths.length > 0) {
      const filePath = filePaths[0];
      const fileName = filePath.split(/[\\/]/).pop();

      if (filePath.endsWith('.py')) {
        // --- Handle Python Script ---
        console.log("Attempting to add Python server:", filePath);
        addMessage(`Attempting to add Python server: ${fileName}`, "system");
        try {
          const response = await fetch(`http://127.0.0.1:${pythonPort}/servers`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({path: filePath}), // Send path for .py
          });
          const data = await response.json();
          if (response.ok && data.status === "success") {
            addMessage(`Server added from ${fileName}. Tools: ${data.tools.length > 0 ? data.tools.join(", ") : 'None'}`, "system");
            await fetchAndRenderServers();
            if (!serverRefreshInterval && pythonPort) {
              serverRefreshInterval = setInterval(fetchAndRenderServers, 10000);
              addMessage("Restarting automatic server refresh.", "system");
            }
          } else {
            throw new Error(data.message || `Failed to add server (status: ${response.status})`);
          }
        } catch (error) {
          console.error("Error adding Python server:", error);
          addMessage(`Error adding Python server ${fileName}: ${error.message}`, "system");
          await fetchAndRenderServers();
        }
      } else if (filePath.endsWith('.json')) {
        // --- Handle JSON File ---
        console.log("Attempting to add servers from JSON:", filePath);
        addMessage(`Attempting to add servers from JSON file: ${fileName}`, "system");
        try {
          const jsonContent = await window.electronAPI.readFileContent(filePath);
          const config = JSON.parse(jsonContent);

          if (!config || typeof config.mcpServers !== 'object') {
            throw new Error("Invalid JSON format. Missing 'mcpServers' object.");
          }

          const serverNames = Object.keys(config.mcpServers);
          if (serverNames.length === 0) {
            addMessage(`No servers found in ${fileName}.`, "system");
            return;
          }

          addMessage(`Found ${serverNames.length} server(s) in ${fileName}. Adding...`, "system");

          let allAddedSuccessfully = true;
          for (const serverName of serverNames) {
            const serverDef = config.mcpServers[serverName];
            if (!serverDef || !serverDef.command || !Array.isArray(serverDef.args)) {
              addMessage(`Skipping invalid server definition for '${serverName}' in ${fileName}. Missing command or args.`, "system");
              allAddedSuccessfully = false;
              continue;
            }

            try {
              const response = await fetch(`http://127.0.0.1:${pythonPort}/servers`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ // Send name, command, args for JSON-defined servers
                  name: serverName,
                  command: serverDef.command,
                  args: serverDef.args
                }),
              });
              const data = await response.json();
              if (response.ok && data.status === "success") {
                 addMessage(`Server '${serverName}' added. Tools: ${data.tools.length > 0 ? data.tools.join(", ") : 'None'}`, "system");
              } else {
                 throw new Error(data.message || `Failed to add server '${serverName}' (status: ${response.status})`);
              }
            } catch (serverAddError) {
               console.error(`Error adding server '${serverName}':`, serverAddError);
               addMessage(`Error adding server '${serverName}': ${serverAddError.message}`, "system");
               allAddedSuccessfully = false;
            }
          } // End for loop

          await fetchAndRenderServers(); // Refresh list after attempting all adds
          if (allAddedSuccessfully && !serverRefreshInterval && pythonPort) {
             serverRefreshInterval = setInterval(fetchAndRenderServers, 10000);
             addMessage("Restarting automatic server refresh.", "system");
          }

        } catch (error) {
          console.error("Error processing JSON server file:", error);
          addMessage(`Error processing ${fileName}: ${error.message}`, "system");
          await fetchAndRenderServers(); // Refresh list even on JSON processing error
        }
      } else {
        addMessage(`Unsupported file type: ${fileName}. Please select a .py or .json file.`, "system");
      }
    }
  });

  // Settings panel functions
  function openSettings() {
    settingsPanel.classList.add("open");
    settingsOverlay.classList.add("active");
    loadCurrentSettings();
  }

  function closeSettings() {
    settingsPanel.classList.remove("open");
    settingsOverlay.classList.remove("active");
  }

  async function loadCurrentSettings() {
    try {
      // Load current settings including backend
      const currentSettings = await window.electronAPI.getCurrentSettings();

      // Set backend
      if (currentSettings.backend && settingsBackendSelect) {
        settingsBackendSelect.value = currentSettings.backend;
        updateUIForBackend(currentSettings.backend);
      }

      // Set API key if available
      if (currentSettings.apiKey) {
        settingsApiKey.value = currentSettings.apiKey;
      }

      // Load available models
      await loadAvailableModels();

      // Set current model
      if (currentSettings.model) {
        settingsModelSelect.value = currentSettings.model;
      }
    } catch (error) {
      console.error("Error loading current settings:", error);
    }
  }

  // Function to update UI based on selected backend
  function updateUIForBackend(backend) {
    const apiKeyLabel = settingsApiKey.parentElement.querySelector('label');

    switch(backend) {
      case 'gemini':
        apiKeyLabel.textContent = 'Gemini API Key:';
        settingsApiKey.placeholder = 'Enter your Gemini API key';
        settingsApiKey.required = true;
        break;
      case 'ollama':
        apiKeyLabel.textContent = 'API Key (Optional):';
        settingsApiKey.placeholder = 'API key not required for local models';
        settingsApiKey.required = false;
        break;
      case 'openai':
        apiKeyLabel.textContent = 'OpenAI API Key:';
        settingsApiKey.placeholder = 'Enter your OpenAI API key';
        settingsApiKey.required = true;
        break;
      case 'mlx':
        apiKeyLabel.textContent = 'API Key (Optional):';
        settingsApiKey.placeholder = 'API key not required for local MLX models';
        settingsApiKey.required = false;
        break;
      case 'anthropic':
        apiKeyLabel.textContent = 'Anthropic API Key:';
        settingsApiKey.placeholder = 'Enter your Anthropic API key';
        settingsApiKey.required = true;
        break;
      case 'cohere':
        apiKeyLabel.textContent = 'Cohere API Key:';
        settingsApiKey.placeholder = 'Enter your Cohere API key';
        settingsApiKey.required = true;
        break;
    }
  }

  async function loadAvailableModels() {
    try {
      settingsModelSelect.innerHTML = '<option value="">Loading models...</option>';
      const models = await window.electronAPI.getAvailableModels();

      settingsModelSelect.innerHTML = '';
      if (models && models.length > 0) {
        // Group models by provider for better organization
        const modelsByProvider = {};
        models.forEach(model => {
          const provider = model.split('/')[0];
          if (!modelsByProvider[provider]) {
            modelsByProvider[provider] = [];
          }
          modelsByProvider[provider].push(model);
        });

        // Add models grouped by provider
        Object.keys(modelsByProvider).sort().forEach(provider => {
          const optgroup = document.createElement('optgroup');
          optgroup.label = provider.charAt(0).toUpperCase() + provider.slice(1);

          modelsByProvider[provider].forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            optgroup.appendChild(option);
          });

          settingsModelSelect.appendChild(optgroup);
        });
      } else {
        settingsModelSelect.innerHTML = '<option value="">No models available</option>';
      }
    } catch (error) {
      console.error("Error loading models:", error);
      settingsModelSelect.innerHTML = '<option value="">Error loading models</option>';
    }
  }

  async function saveSettings() {
    const apiKey = settingsApiKey.value.trim();
    const selectedModel = settingsModelSelect.value;
    const selectedBackend = settingsBackendSelect.value;

    // Validate required fields based on backend
    if (['gemini', 'openai', 'anthropic', 'cohere'].includes(selectedBackend) && !apiKey) {
      addMessage("API key is required for this provider.", "system");
      return;
    }

    try {
      const result = await window.electronAPI.saveApiKey(apiKey, selectedModel, selectedBackend);
      if (result.success) {
        addMessage("Settings saved successfully. Backend re-initialized.", "system");
        closeSettings();
      } else {
        addMessage(`Error saving settings: ${result.message}`, "system");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      addMessage(`Error saving settings: ${error.message}`, "system");
    }
  }

  // Settings panel event listeners
  settingsBtn.addEventListener("click", openSettings);
  closeSettingsBtn.addEventListener("click", closeSettings);
  settingsOverlay.addEventListener("click", closeSettings);
  settingsCancelBtn.addEventListener("click", closeSettings);
  settingsSaveBtn.addEventListener("click", saveSettings);

  // Handle backend selection change
  if (settingsBackendSelect) {
    settingsBackendSelect.addEventListener('change', async () => {
      const selectedBackend = settingsBackendSelect.value;
      updateUIForBackend(selectedBackend);

      // Set the backend on the main process
      try {
        await window.electronAPI.setBackend(selectedBackend);
      } catch (error) {
        console.error("Error setting backend:", error);
      }

      // Reload models for new backend
      settingsModelSelect.innerHTML = '<option value="">Loading models...</option>';
      await loadAvailableModels();
    });
  }

  // Handle Escape key to close settings
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && settingsPanel.classList.contains("open")) {
      closeSettings();
    }
  });

  initializeApp();
});
