# Wallabag Client - TUI Redesign Project

## Overview
This project has been redesigned from a traditional CLI tool into a modern Terminal User Interface (TUI) similar to the pine email client. The TUI provides an intuitive, interactive way to browse and read wallabag articles.

## What We've Accomplished ✅

### 1. **TUI Framework Implementation**
- **Main Application**: Created `src/wallabag/tui.py` with Textual-based TUI
- **Two Screen Architecture**: 
  - `ArticleListScreen`: Pine-like article browser
  - `ArticleViewScreen`: Full article reading view with scrolling
- **Entry Point**: Added `wallabag-tui` command alongside existing `wallabag` CLI

### 2. **Pine-like Interface**
- **Article List View**: Scrollable table showing articles with status indicators
- **Status Characters**: 
  - `N` = New/Unread article
  - `R` = Read article  
  - `*` = Starred article
- **Columns**: ID, Status, Title, Tags, Reading Time
- **Navigation**: j/k keys, arrow keys, Enter/o to read

### 3. **Modern Dependencies**
- **Added Textual**: Modern Python TUI framework (≥0.44.0)
- **Package Configuration**: Updated `setup.py` with new dependency and entry point
- **Maintained Compatibility**: Original `wallabag` command still works

### 4. **Key Bindings (Pine-style)**
```
j/k or ↑/↓     - Navigate article list
Enter/o        - Read selected article
r              - Toggle read status
s              - Toggle star status  
q              - Quit/Back
Page Up/Down   - Scroll article content
Home/End       - Jump to top/bottom of article
```

### 5. **Architecture Integration**
- **Reused Existing API**: All wallabag server communication unchanged
- **Entry Model**: Leveraged existing `Entry` class for data
- **Export System**: Integrated existing article formatting for reading view

## Current Status 🟢 FULLY WORKING

The TUI is **completely functional** and provides:
- ✅ Wallabag articles in scrollable list
- ✅ Article status indicators (read/unread/starred)
- ✅ Professional interface with header/footer and status bar
- ✅ Full keyboard navigation
- ✅ Real-time read/star status toggles with immediate table updates
- ✅ Complete article reading view with formatted content
- ✅ Smooth scrolling through article text
- ✅ Automatic marking as read when viewing articles
- ✅ Error handling and user feedback
- ✅ Successfully loads from existing wallabag configuration

**Installation & Usage:**
```bash
pip install -e .
wallabag-tui
```

## Core Functionality ✅ COMPLETE

### Phase 1: Core Functionality - COMPLETED
1. **✅ Article Reading View**
   - Complete article content loading and display
   - Smooth scrolling through article text
   - Proper text formatting and wrapping
   - Breadcrumb navigation

2. **✅ Action Implementation**
   - Complete read/unread toggle (`r` key) with server sync
   - Complete star/unstar toggle (`s` key) with server sync
   - Real-time status updates in list view
   - Status messages with auto-clear

3. **✅ Navigation Enhancements**
   - Smooth transitions between list and reading views
   - Breadcrumb/status indicators
   - DataTable event handling for Enter key
   - Alternative 'o' key for article opening

### Phase 2: Enhanced Features (Medium Priority)
4. **Filtering & Search**
   - Filter by read/unread status
   - Filter by starred status
   - Filter by tags
   - Simple text search

5. **Pagination & Performance**
   - Load articles in batches
   - Infinite scroll or pagination
   - Lazy loading for large article lists

6. **Visual Improvements**
   - Re-enable CSS styling (`tui.css`)
   - Custom color themes
   - Better status indicators (icons/colors)
   - Article preview in list view

### Phase 3: Advanced Features (Low Priority)
7. **Additional Actions**
   - Add new articles from TUI
   - Tag management
   - Delete articles
   - Export articles

8. **Configuration**
   - TUI-specific settings
   - Keybinding customization
   - Display preferences

9. **Help System**
   - In-app help screen
   - Keyboard shortcut reference
   - Tutorial/getting started

## Technical Implementation Details

### File Structure
```
src/wallabag/
├── tui.py          # Main TUI application (COMPLETE)
├── tui.css         # Styling (disabled for compatibility)
├── wallabag.py     # Original CLI (unchanged)
└── ...             # Existing API/commands (unchanged)
```

### Dependencies
- **textual**: Modern TUI framework (≥0.44.0) - **ADDED TO SETUP.PY**
- **All existing deps**: Maintained for backward compatibility

### Key Technical Solutions
1. **DataTable Event Handling**: Used `on_data_table_row_selected` event instead of Enter key binding to handle table row selection properly
2. **Table Cell Updates**: Implemented proper row/column key mapping using `table.rows.keys()` and `table.columns.keys()` for reliable cell updates
3. **CSS Loading**: Disabled CSS with `CSS = ""` and `CSS_PATH = None` to avoid package inclusion issues
4. **API Integration**: Seamless integration with existing UpdateEntry API for real-time status changes
5. **Configuration Validation**: Added helpful warning message when TUI is run without proper wallabag configuration
6. **Entry Point Management**: Proper setup.py configuration with textual dependency for reliable installation

### Testing Commands
```bash
# Test original CLI still works
wallabag --help
wallabag list

# Test new TUI
wallabag-tui --help
wallabag-tui
```

### Known Issues RESOLVED
- ✅ CSS loading errors fixed
- ✅ Read/star toggle actions fully implemented
- ✅ Article content view complete with scrolling
- ✅ DataTable key binding conflicts resolved
- ✅ Table cell update errors fixed
- ✅ Entry point installation issues resolved
- ✅ Configuration warning message added for first-time users

## Development Guidelines

When working on this project:

1. **Maintain Compatibility**: Don't break existing CLI functionality
2. **Reuse Existing Code**: Leverage the robust API layer already built
3. **Follow Pine UX**: Keep the interface similar to pine email client
4. **Test Both Interfaces**: Ensure both `wallabag` and `wallabag-tui` work
5. **Handle Errors Gracefully**: TUI should show helpful error messages

## Commands for Development

```bash
# Development install (run after any code changes)
pip install -e .

# Test both commands
wallabag --help
wallabag-tui --help

# Setup wallabag configuration (required for TUI)
wallabag config

# Run linting (if available)
# Command not determined yet - check project for existing lint setup
```

## Important Notes for Development

1. **After Code Changes**: Always run `pip install -e .` after modifying source code to refresh entry points
2. **Configuration Required**: The TUI requires wallabag configuration. Run `wallabag config` first
3. **Dependencies**: The textual dependency is now included in setup.py and will be installed automatically

---

## Project Completion Summary

This TUI project has been **successfully completed** and transforms the wallabag client from a command-line tool into a fully functional, interactive terminal interface that makes browsing and reading articles much more enjoyable.

### What Works Now:
- 🎯 **Complete pine-style interface** with familiar navigation
- 📖 **Full article reading** with formatted content and scrolling
- ⚡ **Real-time status updates** for read/star toggles
- 🔄 **Seamless server synchronization** 
- 🎨 **Professional UI** with status indicators and feedback
- ⌨️ **Intuitive keyboard shortcuts** matching pine conventions

The TUI is production-ready and provides a modern, efficient way to manage your wallabag articles directly from the terminal.