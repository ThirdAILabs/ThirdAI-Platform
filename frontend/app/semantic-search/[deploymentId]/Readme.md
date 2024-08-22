The goal of this exercise is to give the RAG frontend a consistent look and feel with the rest of the platform by using components from the thirdai platform template.

Here is an example of how we changed the implementation of the RAG frontend (previously in `ThirdAI-Platform/neuraldb_frontend`, but moved into `ThirdAI-Platform/frontend/semantic-search` in the `ndb-frontend branch`) to use components from the thirdai platform template:
[Before using template components](https://github.com/ThirdAILabs/ThirdAI-Platform/blob/frontend-bug-admin-workflow/neuraldb_frontend/src/components/SearchBar.tsx) vs
[After using template components](https://github.com/ThirdAILabs/ThirdAI-Platform/blob/ndb-frontend/frontend/app/semantic-search/%5BdeploymentId%5D/components/SearchBar.tsx)

The template components are found in [`frontend/components/ui`](https://github.com/ThirdAILabs/ThirdAI-Platform/tree/ndb-frontend/frontend/components/ui)

These components are built on top of Radix UI and mostly retain the same interfaces, so you can read the Radix UI documentation to see how to use these components. E.g., to see how you can use the DropdownMenu component used in the permalinks above, you can refer to this documentation [https://www.radix-ui.com/primitives/docs/components/dropdown-menu](https://www.radix-ui.com/primitives/docs/components/dropdown-menu)

The template itself is from Vercel, this one in particular: https://vercel.com/templates/next.js/admin-dashboard-tailwind-postgres-react-nextjs

I recognize the RAG frontend is not organized very well. I suggest trying to understand the code by starting at ThirdAI-Platform/frontend/semantic-search/[deploymentId]/page.tsx file and digging deeper from there. 

Keep in mind that it is very likely that the PDF reader will not work for you. That is fine. You can continue working on changing the styling of the rest of the page. If you have time and are interested, though, you can try to fix the PDF reader.