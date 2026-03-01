# Breakdown Selection Process

The breakdown selection process allows users to explore the impact or production of an entity in a hierarchical and interactive manner. This document explains the underlying mechanism of this feature.

## 1. The `FullQc` Component

The core of this functionality resides in the `FullQc.svelte` component. It orchestrates the display of the breakdown options and the visualization of the data tree.

## 2. Breakdown Options

The available breakdown options are not hardcoded. They are defined in a `breakdownOptions` object that is loaded from the backend. This object has a tree-like structure, where each node represents a breakdown dimension (e.g., "by country", "by author") and may contain children nodes for further breakdowns.

## 3. User Interaction and State Management

- **`selectedBreakdowns`**: An array that stores the user's current selection path in the breakdown tree. Each element in the array is a string identifier for a chosen breakdown option.
- **`updateLevelSpecs` function**: This function is responsible for determining which breakdown options are available at each level of the hierarchy. It traverses the `breakdownOptions` tree based on the current `selectedBreakdowns` and prepares the `levelOptions` for the next level.
- **`MidpathBar` component**: This component renders the available breakdown options to the user.

When a user clicks on a breakdown option, the `selectedBreakdowns` array is updated. This triggers a series of reactive updates.

## 4. Dynamic Tree Loading

In some cases, a specific combination of breakdowns may require a different data tree structure.

- **`updateTreeSpecId` function**: This function is triggered whenever `selectedBreakdowns` changes. It checks if the new selection path requires a different tree structure (identified by a `treeId`).
- **`loadNewQc` function**: If a new `treeId` is determined, this function is called to fetch the corresponding tree data from the backend.

## 5. Semantic Descriptions

To present the breakdown options in a more intuitive and human-readable way, the raw option identifiers are transformed into semantic descriptions.

- **`semantify` function**: Located in `src/lib/text-format-util.ts`, this function takes a breakdown option identifier and the current selection path as input.
- **`SEM_MAP`**: The `semantify` function uses a large, nested map called `SEM_MAP` to look up the appropriate semantic text. This map is structured hierarchically to match the breakdown option tree, allowing for context-aware descriptions.

For example, instead of displaying a raw option like `"countries-false"`, the user might see a more descriptive text like `"are cited by authors working in"`, depending on the previous selections. This makes the exploration process more engaging and easier to understand.
