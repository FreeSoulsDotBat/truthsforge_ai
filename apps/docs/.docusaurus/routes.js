import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/docs',
    component: ComponentCreator('/docs', 'c9f'),
    routes: [
      {
        path: '/docs',
        component: ComponentCreator('/docs', '402'),
        routes: [
          {
            path: '/docs',
            component: ComponentCreator('/docs', 'cb4'),
            routes: [
              {
                path: '/docs/3d-mcp-modeling',
                component: ComponentCreator('/docs/3d-mcp-modeling', 'dc7'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/api',
                component: ComponentCreator('/docs/api', 'ebd'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/application-map',
                component: ComponentCreator('/docs/application-map', '7c4'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/architecture',
                component: ComponentCreator('/docs/architecture', 'f8b'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/chatgpt-import',
                component: ComponentCreator('/docs/chatgpt-import', '658'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/decisions',
                component: ComponentCreator('/docs/decisions', 'f95'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/deep-research',
                component: ComponentCreator('/docs/deep-research', '434'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/infra-observability',
                component: ComponentCreator('/docs/infra-observability', '833'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/knowledge-bases',
                component: ComponentCreator('/docs/knowledge-bases', '8bd'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/local-dev',
                component: ComponentCreator('/docs/local-dev', 'fd7'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/mvp-readiness',
                component: ComponentCreator('/docs/mvp-readiness', '6e4'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/reasoning-summary',
                component: ComponentCreator('/docs/reasoning-summary', '407'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/docs/roadmap',
                component: ComponentCreator('/docs/roadmap', 'c2e'),
                exact: true,
                sidebar: "docsSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '/',
    component: ComponentCreator('/', 'e5f'),
    exact: true
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
