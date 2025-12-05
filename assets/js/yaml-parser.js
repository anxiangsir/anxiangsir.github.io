/**
 * Minimal YAML parser for publications data
 * Supports basic YAML structure used in the publications files
 */

function parseYAML(yamlText) {
    const lines = yamlText.split('\n');
    const result = { publications: [] };
    let currentPub = null;
    let currentKey = null;
    let multilineValue = [];
    let inMultiline = false;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        
        // Skip empty lines and root key
        if (!trimmed || trimmed === 'publications:') {
            continue;
        }
        
        // New publication item
        if (line.match(/^  - title:/)) {
            // Save previous publication if exists
            if (currentPub) {
                if (inMultiline && currentKey) {
                    currentPub[currentKey] = multilineValue.join('\n').trim();
                }
                result.publications.push(currentPub);
            }
            currentPub = {};
            multilineValue = [];
            inMultiline = false;
            
            // Get title value
            const match = line.match(/^  - title:\s*"?(.+?)"?$/);
            if (match) {
                currentPub.title = match[1].replace(/^["']|["']$/g, '');
            }
        }
        // Key-value pairs
        else if (currentPub && line.match(/^    \w+:/)) {
            // Save previous multiline if exists
            if (inMultiline && currentKey) {
                currentPub[currentKey] = multilineValue.join('\n').trim();
                multilineValue = [];
            }
            
            const match = line.match(/^    (\w+):\s*(.*)$/);
            if (match) {
                const key = match[1];
                let value = match[2];
                
                // Check if this is the start of a multiline value
                if (value === '|') {
                    inMultiline = true;
                    currentKey = key;
                    multilineValue = [];
                } else {
                    inMultiline = false;
                    currentKey = null;
                    // Remove surrounding quotes if present
                    value = value.replace(/^["']|["']$/g, '');
                    currentPub[key] = value;
                }
            }
        }
        // Multiline content
        else if (inMultiline && line.match(/^      /)) {
            const content = line.substring(6); // Remove 6 spaces indentation
            multilineValue.push(content);
        }
    }
    
    // Add the last publication
    if (currentPub) {
        if (inMultiline && currentKey) {
            currentPub[currentKey] = multilineValue.join('\n').trim();
        }
        result.publications.push(currentPub);
    }
    
    return result;
}
