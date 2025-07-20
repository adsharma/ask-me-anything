// settings.js
document.addEventListener("DOMContentLoaded", async () => {
  const backendSelect = document.getElementById("backend-select");
  const apiKeyInput = document.getElementById("api-key");
  const modelSelect = document.getElementById("model-select");
  const saveBtn = document.getElementById("save-btn");
  const cancelBtn = document.getElementById("cancel-btn");

  let modelHelpers = {};

  // Load model helpers
  try {
    modelHelpers = await window.settingsAPI.getModelHelpers();
  } catch (error) {
    console.error("Error loading model helpers:", error);
  }

  // Function to update labels and help text based on backend
  function updateUIForBackend(backend) {
    const apiKeyGroup = apiKeyInput.parentElement;
    const helpText = apiKeyGroup.querySelector('.help-text');
    const apiKeyLabel = apiKeyGroup.querySelector('label');

    switch(backend) {
      case 'gemini':
        apiKeyLabel.textContent = 'Gemini API Key:';
        helpText.textContent = 'Enter your Google Gemini API key';
        apiKeyInput.required = true;
        break;
      case 'ollama':
        apiKeyLabel.textContent = 'API Key (Optional):';
        helpText.textContent = 'API key not required for local Ollama models';
        apiKeyInput.required = false;
        break;
      case 'openai':
        apiKeyLabel.textContent = 'OpenAI API Key:';
        helpText.textContent = 'Enter your OpenAI API key';
        apiKeyInput.required = true;
        break;
      case 'mlx':
        apiKeyLabel.textContent = 'API Key (Optional):';
        helpText.textContent = 'API key not required for local MLX models via OpenAI-compatible server';
        apiKeyInput.required = false;
        break;
      case 'anthropic':
        apiKeyLabel.textContent = 'Anthropic API Key:';
        helpText.textContent = 'Enter your Anthropic API key';
        apiKeyInput.required = true;
        break;
      case 'cohere':
        apiKeyLabel.textContent = 'Cohere API Key:';
        helpText.textContent = 'Enter your Cohere API key';
        apiKeyInput.required = true;
        break;
    }
  }

  // Function to format model names for display
  function formatModelForDisplay(fullModelName) {
    if (!modelHelpers.parseModelName) return fullModelName;

    const parsed = modelHelpers.parseModelName(fullModelName);
    return `${parsed.model} (${parsed.provider})`;
  }

  // Function to populate the model dropdown
  async function populateModels() {
    try {
      modelSelect.disabled = true;
      modelSelect.innerHTML = '<option value="">Loading models...</option>';

      const availableModels = await window.settingsAPI.listModels();
      const currentModel = await window.settingsAPI.getModel();

      modelSelect.innerHTML = '';

      if (!availableModels || availableModels.length === 0) {
         modelSelect.innerHTML = '<option value="">No models available</option>';
         return;
      }

      // Group models by provider for better organization
      const modelsByProvider = {};
      availableModels.forEach(model => {
        const provider = modelHelpers.getProviderFromModel ?
          modelHelpers.getProviderFromModel(model) :
          model.split('/')[0];

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
          if (model === currentModel) {
            option.selected = true;
          }
          optgroup.appendChild(option);
        });

        modelSelect.appendChild(optgroup);
      });

      modelSelect.disabled = false;

    } catch (error) {
      console.error("Error populating models:", error);
      modelSelect.innerHTML = `<option value="">Error loading models</option>`;
    }
  }

  // Load current backend and set up UI
  try {
    const currentBackend = await window.settingsAPI.getCurrentBackend();
    backendSelect.value = currentBackend;
    updateUIForBackend(currentBackend);
  } catch (error) {
    console.error("Error loading current backend:", error);
  }

  // Handle backend change
  backendSelect.addEventListener('change', async () => {
    const selectedBackend = backendSelect.value;
    updateUIForBackend(selectedBackend);

    // Clear model dropdown and reload models for new backend
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    try {
      // Set the backend on the server side first so it knows which models to list
      await window.settingsAPI.setBackend(selectedBackend);
      // Then populate models for the new backend
      await populateModels();
    } catch (error) {
      console.error("Error changing backend:", error);
      modelSelect.innerHTML = '<option value="">Error loading models</option>';
    }
  });

  // Populate models when the dialog loads
  await populateModels();


  saveBtn.addEventListener("click", async () => { // Make async
    const apiKey = apiKeyInput.value;
    const selectedModel = modelSelect.value;
    const selectedBackend = backendSelect.value;

    // Validate required fields based on backend
    if ((selectedBackend === 'gemini' || selectedBackend === 'openai' || selectedBackend === 'anthropic' || selectedBackend === 'cohere') && !apiKey) {
      alert('API key is required for this provider');
      return;
    }

    // Disable buttons during save
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    let modelSetSuccess = true;
    let keySetSuccess = true;
    let backendSetSuccess = true;

    try {
      // Set backend, API key, and model
      console.log(`Attempting to save: Backend=${selectedBackend}, Model=${selectedModel}`);

      // Use the new save method that handles backend + api key + model together
      const result = await window.settingsAPI.saveSettings ?
        await window.settingsAPI.saveSettings(apiKey, selectedModel, selectedBackend) :
        // Fallback to individual calls if saveSettings not available
        await handleIndividualSave(apiKey, selectedModel, selectedBackend);

      if (result.success) {
        console.log("Settings saved successfully");
      } else {
        throw new Error(result.message || "Failed to save settings");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
      alert(`Error saving settings: ${error.message}`);
      backendSetSuccess = false;
    }

    // Re-enable buttons
    saveBtn.disabled = false;
    cancelBtn.disabled = false;
    saveBtn.textContent = "Save";

    // Close dialog only if everything succeeded
    if (backendSetSuccess) {
       window.settingsAPI.closeDialog();
    }
  });

  // Fallback function for individual API calls
  async function handleIndividualSave(apiKey, selectedModel, selectedBackend) {
    // Set backend first
    if (selectedBackend) {
      await window.settingsAPI.setBackend(selectedBackend);
    }

    // Set model if provided
    if (selectedModel) {
      await window.settingsAPI.setModel(selectedModel);
    }

    // Set API key if provided
    if (apiKey) {
      window.settingsAPI.saveKey(apiKey);
    }

    return { success: true, message: "Settings saved successfully" };
  }

  cancelBtn.addEventListener("click", () => {
    window.settingsAPI.closeDialog();
  });

  // Handle Enter/Escape in input fields
  const handleKeyDown = (event) => {
     if (event.key === "Enter") {
      saveBtn.click();
    } else if (event.key === "Escape") {
      cancelBtn.click();
    }
  }
  apiKeyInput.addEventListener("keydown", handleKeyDown);
  modelSelect.addEventListener("keydown", handleKeyDown);
  backendSelect.addEventListener("keydown", handleKeyDown);

  apiKeyInput.focus(); // Focus the API key input first
});
