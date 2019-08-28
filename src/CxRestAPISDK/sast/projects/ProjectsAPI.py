# encoding: utf-8
import http
import json
import copy


import requests

from requests_toolbelt import MultipartEncoder
from pathlib import Path

from ...config import CxConfig
from ...auth import AuthenticationAPI
from ...team.TeamAPI import TeamAPI
from ...exceptions.CxError import BadRequestError, NotFoundError, UnknownHttpStatusError
from .dto import CxUpdateProjectNameTeamIdRequest, CxCreateProjectResponse, \
    CxIssueTrackingSystemDetail, CxSharedRemoteSourceSettingsRequest, CxIssueTrackingSystemField, \
    CxSharedRemoteSourceSettingsResponse, CxGitSettings, \
    CxIssueTrackingSystemType, CxIssueTrackingSystemFieldAllowedValue, CxSourceSettingsLink, \
    CxCreateProjectRequest, CxIssueTrackingSystem, CxLink, CxProject, CxCustomRemoteSourceSettings, \
    CxUpdateProjectRequest, CxProjectExcludeSettings, CxCredential, CxSVNSettings, CxURI, CxPerforceSettings, \
    CxTFSSettings, CxIssueTrackingSystemJira
from .dto.presets import CxPreset

default_team_id = TeamAPI().get_team_id_by_full_name()


class ProjectsAPI(object):
    """
    the projects API
    """
    max_try = CxConfig.CxConfig.config.max_try
    base_url = CxConfig.CxConfig.config.url
    projects_url = base_url + "/projects"
    project_url = base_url + "/projects/{id}"
    project_branch_url = base_url + "/projects/{id}/branch"
    issue_tracking_systems_url = base_url + "/issueTrackingSystems"
    issue_tracking_systems_metadata_url = base_url + "/issueTrackingSystems/{id}/metadata"
    exclude_settings_url = base_url + "/projects/{id}/sourceCode/excludeSettings"
    remote_settings_git_url = base_url + "/projects/{id}/sourceCode/remoteSettings/git"
    remote_settings_svn_url = base_url + "/projects/{id}/sourceCode/remoteSettings/svn"
    remote_settings_tfs_url = base_url + "/projects/{id}/sourceCode/remoteSettings/tfs"
    remote_settings_custom_url = base_url + "/projects/{id}/sourceCode/remoteSettings/custom"
    remote_settings_shared_url = base_url + "/projects/{id}/sourceCode/remoteSettings/shared"
    remote_settings_perforce_url = base_url + "/projects/{id}/sourceCode/remoteSettings/perforce"
    remote_settings_git_ssh_url = base_url + "/projects/{id}/sourceCode/remoteSettings/git/ssh"
    remote_settings_svn_ssh_url = base_url + "/projects/{id}/sourceCode/remoteSettings/svn/ssh"
    attachments_url = base_url + "/projects/{id}/sourceCode/attachments"

    data_retention_settings_url = base_url + "/projects/{id}/dataRetentionSettings"
    jira_url = base_url + "/projects/{id}/issueTrackingSettings/jira"
    presets_url = base_url + "/sast/presets"
    preset_url = base_url + "/sast/presets/{id}"

    def __init__(self):
        """

        """
        self.retry = 0

    def get_all_project_details(self, project_name=None, team_id=default_team_id):
        """
        REST API: get all project details.
        For argument team_id, please consider using TeamAPI.get_team_id_by_full_name(team_full_name)

        Args:
            project_name (str):
            team_id (int):

        Returns:
            :obj:`list` of :obj:`CxProject`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        all_projects = []

        if project_name and team_id:
            self.projects_url += "?projectName=" + str(project_name) + "&teamId=" + str(team_id)

        r = requests.get(self.projects_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == http.HTTPStatus.OK:
            a_list = r.json()
            all_projects = [
                CxProject.CxProject(
                    project_id=item.get("id"),
                    team_id=item.get("teamId"),
                    name=item.get("name"),
                    is_public=item.get("isPublic"),
                    source_settings_link=CxSourceSettingsLink.CxSourceSettingsLink(
                        (item.get("sourceSettingsLink", {}) or {}).get("type"),
                        (item.get("sourceSettingsLink", {}) or {}).get("rel"),
                        (item.get("sourceSettingsLink", {}) or {}).get("uri")
                    ),
                    link=CxLink.CxLink(
                        (item.get("link", {}) or {}).get("rel"),
                        (item.get("link", {}) or {}).get("uri")
                    )
                ) for item in a_list
            ]
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_all_project_details()
        else:
            raise UnknownHttpStatusError()

        return all_projects

    def create_project_with_default_configuration(self, name, owning_team=default_team_id, is_public=True):
        """
        REST API: create project
        :param name: str
        :param owning_team: int
            the owning_team is the team_id
        :param is_public: boolean
        :return: CxCreateProjectResponse

        Args:
            name (str):
            owning_team (int): team id
            is_public (bool):

        Returns:
            :obj:`CxCreateProjectResponse`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        project = None

        req_data = CxCreateProjectRequest.CxCreateProjectRequest(name, owning_team, is_public).get_post_data()
        r = requests.post(
            url=self.projects_url,
            data=req_data,
            headers=AuthenticationAPI.AuthenticationAPI.auth_headers
        )
        if r.status_code == http.HTTPStatus.CREATED:
            d = r.json()
            project = CxCreateProjectResponse.CxCreateProjectResponse(
                d.get("id"),
                CxLink.CxLink(
                    rel=(d.get("link", {}) or {}).get("rel"),
                    uri=(d.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.create_project_with_default_configuration(name, owning_team, is_public)
        else:
            raise UnknownHttpStatusError()

        return project

    def get_project_id_by_name(self, project_name, team_id=default_team_id):
        """
        utility provided by SDK: get project id by project name, and team id

        Args:
            project_name (str): project name under one team, different teams may have projects of the same name
            team_id (int): you can get team_id by using TeamAPI.get_team_id_by_full_name

        Returns:
            int: project id
        """
        all_projects = self.get_all_project_details()
        # a_dict, key is {project_name}&{team_id}, value is project_id
        a_dict = {(project.name + "&" + str(project.team_id)): project.project_id for project in all_projects}
        the_key = project_name + "&" + str(team_id)
        return a_dict.get(the_key)

    def get_project_details_by_id(self, project_id):
        """
        REST API: get project details by project id

        Args:
            project_id (int): consider using get_project_id_by_name to get project_id

        Returns:
            :obj:`CxProject`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError

        """
        project = None
        self.project_url = self.project_url.format(id=project_id)

        r = requests.get(self.project_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == http.HTTPStatus.OK:
            a_dict = r.json()
            project = CxProject.CxProject(
                project_id=a_dict.get("id"),
                team_id=a_dict.get("teamId"),
                name=a_dict.get("name"),
                is_public=a_dict.get("isPublic"),
                source_settings_link=CxSourceSettingsLink.CxSourceSettingsLink(
                    source_settings_link_type=(a_dict.get("sourceSettingsLink", {}) or {}).get("type"),
                    rel=(a_dict.get("sourceSettingsLink", {}) or {}).get("rel"),
                    uri=(a_dict.get("sourceSettingsLink", {}) or {}).get("uri")
                ),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri"),
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_project_details_by_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return project

    def update_project_by_id(self, project_id, name, owning_team=default_team_id, custom_field_id=None,
                             custom_field_value=None):
        """
        update project info by project id
        :param project_id: int
            consider using get_project_id_by_name to get project_id
        :param name: str
            the project name that you want the current project change to
        :param owning_team: int
            the team id that you want the current project change to
        :param custom_field_id: int
            the id of the custom field that you want to change,
            consider using CustomFieldsAPI.get_custom_field_id_by_name
        :param custom_field_value: str
            the value of the custom field that you want to change to
        :return:

        Args:
            project_id (int): consider using get_project_id_by_name to get project_id
            name (str): the project name that you want the current project change to
            owning_team (int): the team id that you want the current project change to
            custom_field_id (int): the id of the custom field that you want to change,
                                    consider using CustomFieldsAPI.get_custom_field_id_by_name
            custom_field_value (str): the value of the custom field that you want to change to

        Returns:
            bool: True means successful, False means not successful

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.project_url = self.project_url.format(id=project_id)

        request_body = CxUpdateProjectRequest.CxUpdateProjectRequest(
            name=name,
            owning_team=owning_team,
            custom_field_id=custom_field_id,
            custom_field_value=custom_field_value
        ).get_post_data()

        r = requests.put(url=self.project_url, data=request_body,
                         headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        # In Python http module, HTTP status ACCEPTED is 202
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.update_project_by_id(project_id, name, owning_team, custom_field_id, custom_field_value)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def update_project_name_team_id(self, project_id, project_name, team_id=default_team_id):
        """
        REST API: update project name, team id

        Args:
            project_id (int): consider using ProjectsAPI.get_project_id_by_name
            project_name (str): the project name to change to
            team_id (int): the project id to change to

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """

        is_successful = False

        self.project_url = self.project_url.format(id=project_id)

        request_body = CxUpdateProjectNameTeamIdRequest.CxUpdateProjectNameTeamIdRequest(
            project_name=project_name,
            owning_team=team_id
        ).get_post_data()

        r = requests.patch(url=self.project_url, data=request_body,
                           headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        # In Python http module, HTTP status ACCEPTED is 202
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.update_project_name_team_id(project_id, project_name, team_id)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def delete_project_by_id(self, project_id, delete_running_scans=False):
        """
        REST API: delete project by id


        Args:
            project_id (int):
            delete_running_scans (bool):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.project_url = self.project_url.format(id=project_id)

        request_body = json.dumps({"deleteRunningScans": delete_running_scans})

        r = requests.delete(url=self.project_url, data=request_body,
                            headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        # In Python http module, HTTP status ACCEPTED is 202
        if r.status_code == 202:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.delete_project_by_id(project_id, delete_running_scans)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def create_branched_project(self, project_id, branched_project_name):
        """
        Create a branch of an existing project.

        Args:
            project_id (int):
            branched_project_name (str): specifies the name of the branched project
        Returns:
            :obj:`CxCreateProjectResponse`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError

        """
        project = None

        self.project_branch_url = self.project_branch_url.format(id=project_id)

        request_body = json.dumps({"name": branched_project_name})

        r = requests.post(url=self.project_branch_url, data=request_body,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 201:
            a_dict = r.json()
            project = CxCreateProjectResponse.CxCreateProjectResponse(
                project_id=a_dict.get("id"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.create_branched_project(project_id, branched_project_name)
        else:
            raise UnknownHttpStatusError()

        return project

    def get_all_issue_tracking_systems(self):
        """
        Get details of all issue tracking systems (e.g. Jira) currently registered to CxSAST.

        Returns:
            :obj:`list` of :obj:`CxIssueTrackingSystem`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError

        """
        issue_tracking_systems = []

        r = requests.get(url=self.issue_tracking_systems_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_list = r.json()
            issue_tracking_systems = [
                CxIssueTrackingSystem.CxIssueTrackingSystem(
                    tracking_system_id=item.get("id"),
                    name=item.get("name"),
                    tracking_system_type=item.get("type"),
                    url=item.get("url")
                ) for item in a_list
            ]
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_all_issue_tracking_systems()
        else:
            raise UnknownHttpStatusError()

        return issue_tracking_systems

    def get_issue_tracking_system_id_by_name(self, name):
        """
        get issue tracking system id by name

        Args:
            name (str): issue tracking system name

        Returns:
            int: issue_tracking_system id
        """
        issue_tracking_systems = self.get_all_issue_tracking_systems()
        a_dict = {item.name: item.id for item in issue_tracking_systems}
        return a_dict.get(name)

    def get_issue_tracking_system_details_by_id(self, issue_tracking_system_id):
        """
        Get metadata for a specific issue tracking system (e.g. Jira) according to the Issue Tracking System Id.
        :param issue_tracking_system_id: int
        :return:

        Args:
            issue_tracking_system_id (int):

        Returns:
            dict

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO Check, when have jira
        issue_tracking_system = None

        self.issue_tracking_systems_metadata_url = self.issue_tracking_systems_metadata_url.format(
            id=issue_tracking_system_id
        )

        r = requests.get(url=self.issue_tracking_systems_metadata_url,
                         headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_list = r.json().get("projects")
            if a_list:
                a_dict = a_list[0]
                issue_types = a_dict.get("issueTypes")
                issue_type = issue_types[0] if issue_types else {}
                fields = issue_type.get("fields")
                field = fields[0] if fields else {}
                allowed_values = field.get("allowedValues")

                c = CxIssueTrackingSystemFieldAllowedValue

                issue_tracking_system = {
                    "projects": [
                        CxIssueTrackingSystemDetail.CxIssueTrackingSystemDetail(
                            tracking_system_detail_id=a_dict.get("id"),
                            name=a_dict.get("name"),
                            issue_types=[
                                CxIssueTrackingSystemType.CxIssueTrackingSystemType(
                                    issue_tracking_system_type_id=issue_type.get("id"),
                                    name=issue_type.get("name"),
                                    sub_task=issue_type.get("subtask"),
                                    fields=[
                                        CxIssueTrackingSystemField.CxIssueTrackingSystemField(
                                            tracking_system_field_id=field.get("id"),
                                            name=field.get("name"),
                                            multiple=field.get("multiple"),
                                            required=field.get("required"),
                                            supported=field.get("supported"),
                                            allowed_values=[
                                                c.CxIssueTrackingSystemFieldAllowedValue(
                                                    allowed_value_id=item.get("id"),
                                                    name=item.get("name")
                                                ) for item in allowed_values
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                }
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_issue_tracking_system_details_by_id(issue_tracking_system_id)
        else:
            raise UnknownHttpStatusError()

        return issue_tracking_system

    def get_project_exclude_settings_by_project_id(self, project_id):
        """
        get details of a project's exclude folders/files settings according to the project Id.
        :param project_id:
        :return:

        Args:
            project_id (int):

        Returns:
            :obj:`CxProjectExcludeSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """

        project_exclude_settings = None

        self.exclude_settings_url = self.exclude_settings_url.format(id=project_id)
        r = requests.get(url=self.exclude_settings_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_dict = r.json()
            project_exclude_settings = CxProjectExcludeSettings.CxProjectExcludeSettings(
                project_id=a_dict.get("projectId"),
                exclude_folders_pattern=a_dict.get("excludeFoldersPattern"),
                exclude_files_pattern=a_dict.get("excludeFilesPattern"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_project_exclude_settings_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return project_exclude_settings

    def set_project_exclude_settings_by_project_id(self, project_id, exclude_folders_pattern, exclude_files_pattern):
        """
        set a project's exclude folders/files settings according to the project Id.

        Args:
            project_id (int):
            exclude_folders_pattern (str):
            exclude_files_pattern (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.exclude_settings_url = self.exclude_settings_url.format(id=project_id)
        body_data = json.dumps(
            {
                "excludeFoldersPattern": exclude_folders_pattern,
                "excludeFilesPattern": exclude_files_pattern
            }
        )
        r = requests.put(url=self.exclude_settings_url, data=body_data,
                         headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == 200:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_project_exclude_settings_by_project_id(project_id, exclude_folders_pattern, exclude_files_pattern)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_git_by_project_id(self, project_id):
        """
        Get a specific project's remote source settings for a GIT repository according to the Project Id.
        :param project_id: int
        :return:

        Args:
            project_id (int):

        Returns:
            :obj:`CxGitSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        git_settings = None

        self.remote_settings_git_url = self.remote_settings_git_url.format(id=project_id)
        r = requests.get(url=self.remote_settings_git_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_dict = r.json()
            git_settings = CxGitSettings.CxGitSettings(
                url=a_dict.get("url"),
                branch=a_dict.get("branch"),
                use_ssh=a_dict.get("useSsh"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_git_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return git_settings

    def set_remote_source_setting_to_git(self, project_id, url, branch, private_key=None):
        """
        Set a specific project's remote source location to a GIT repository using SSH protocol.
        :param project_id: str
        :param url: str
            The url which is used to connect to the GIT repository (e.g. git@github.com:test/repo.git)
        :param branch: str
            The branch of a GIT repository (e.g. refs/heads/master)
        :param private_key: str
            The private key (optional) which is used to connect to the GIT repository using SSH protocol
        :return:

        Args:
            project_id (int):
            url (str): The url which is used to connect to the GIT repository (e.g. git@github.com:test/repo.git)
            branch (str): The branch of a GIT repository (e.g. refs/heads/master)
            private_key (str): The private key (optional) which is used to connect to the GIT repository using
                                SSH protocol

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """

        is_successful = False

        self.remote_settings_git_url = self.remote_settings_git_url.format(id=project_id)

        post_body = CxGitSettings.CxGitSettings(
            url=url, branch=branch, private_key=private_key
        ).get_post_data()

        r = requests.post(url=self.remote_settings_git_url, data=post_body,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_setting_to_git(project_id, url, branch, private_key)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_svn_by_project_id(self, project_id):
        """
        get a specific project's remote source location settings for SVN repository according to the Project Id.

        Args:
            project_id (int):

        Returns:
            :obj:`CxSVNSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """

        svn_settings = None

        self.remote_settings_svn_url = self.remote_settings_svn_url.format(id=project_id)
        r = requests.get(url=self.remote_settings_svn_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_dict = r.json()
            svn_settings = CxSVNSettings.CxSVNSettings(
                uri=CxURI.CxURI(
                    absolute_url=(a_dict.get("uri", {}) or {}).get("absoluteUrl"),
                    port=(a_dict.get("uri", {}) or {}).get("port")
                ),
                paths=a_dict.get("paths", []),
                use_ssh=a_dict.get("useSsh", False),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_svn_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return svn_settings

    def set_remote_source_settings_to_svn(self, project_id, absolute_url, port, paths, username, password,
                                          private_key=None):
        """
        set a specific project's remote source location to a SVN repository using SSH protocol.

        Args:
            project_id (int):
            absolute_url (str):
            port (int):
            paths (:obj:`lsit` of :obj:`str`):
            username (str):
            password (str):
            private_key (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.remote_settings_svn_url = self.remote_settings_svn_url.format(id=project_id)

        post_body_data = CxSVNSettings.CxSVNSettings(
            uri=CxURI.CxURI(
                absolute_url=absolute_url,
                port=port
            ),
            paths=paths,
            credentials=CxCredential.CxCredential(
                username=username,
                password=password
            ),
            private_key=private_key
        ).get_post_data()

        r = requests.post(url=self.remote_settings_svn_url,
                          data=post_body_data,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_settings_to_svn(project_id, absolute_url, port, paths, username, password,
                                                   private_key)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_tfs_by_project_id(self, project_id):
        """
        Get a specific project's remote source location settings for TFS repository according to the Project Id.

        Args:
            project_id (int):

        Returns:
            :obj:`CxTFSSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO, check, when have TFS environment

        tfs_settings = None

        if project_id:
            self.remote_settings_tfs_url = self.remote_settings_tfs_url.format(id=project_id)

        r = requests.get(url=self.remote_settings_tfs_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == 200:
            a_dict = r.json()
            tfs_settings = CxTFSSettings.CxTFSSettings(
                uri=CxURI.CxURI(
                    absolute_url=(a_dict.get("uri", {}) or {}).get("absoluteUrl"),
                    port=(a_dict.get("uri", {}) or {}).get("port"),
                ),
                paths=a_dict.get("paths"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_tfs_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return tfs_settings

    def set_remote_source_settings_to_tfs(self, project_id, username, password, absolute_url, port, paths):
        """
        Set a specific project's remote source location to a TFS repository.

        Args:
            project_id (int):
            username (str):
            password (str):
            absolute_url (str):
            port (int):
            paths (:obj:`list` of :obj:`str`):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO, check, when have TFS environment
        is_successful = False

        if project_id:
            self.remote_settings_tfs_url = self.remote_settings_tfs_url.format(id=project_id)

        post_data = CxTFSSettings.CxTFSSettings(
            credentials=CxCredential.CxCredential(
                username=username,
                password=password
            ),
            uri=CxURI.CxURI(
                absolute_url=absolute_url,
                port=port
            ),
            paths=paths
        ).get_post_data()

        r = requests.post(
            url=self.remote_settings_tfs_url,
            headers=AuthenticationAPI.AuthenticationAPI.auth_headers,
            data=post_data
        )
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_settings_to_tfs(project_id, username, password, absolute_url, port, paths)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_custom_by_project_id(self, project_id):
        """
        Get a specific project's remote source location settings for custom repository (e.g. source pulling)
         according to the Project Id.
        :param project_id:
        :return:

        Args:
            project_id (int):

        Returns:
            :obj:`CxCustomRemoteSourceSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        custom_remote_setting = None

        self.remote_settings_custom_url = self.remote_settings_custom_url.format(id=project_id)
        r = requests.get(url=self.remote_settings_custom_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_dict = r.json()
            custom_remote_setting = CxCustomRemoteSourceSettings.CxCustomRemoteSourceSettings(
                path=a_dict.get("path"),
                pulling_command_id=a_dict.get("pullingCommandId"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_custom_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return custom_remote_setting

    def set_remote_source_setting_for_custom_by_project_id(self, project_id, path,
                                                           pre_scan_command_id, username, password):
        """
        Set a specific project's remote source location settings for custom repository
        (e.g. source pulling) according to the Project Id.


        Args:
            project_id (int):
            path (str):
            pre_scan_command_id (int):
            username (str):
            password (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.remote_settings_custom_url = self.remote_settings_custom_url.format(id=project_id)
        request_body_data = CxCustomRemoteSourceSettings.CxCustomRemoteSourceSettings(
            path=path,
            pulling_command_id=pre_scan_command_id,
            credentials=CxCredential.CxCredential(
                username=username,
                password=password
            )
        ).get_post_data()

        r = requests.post(url=self.remote_settings_custom_url, data=request_body_data,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_setting_for_custom_by_project_id(project_id, path,
                                                                    pre_scan_command_id, username, password)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_shared_by_project_id(self, project_id):
        """
        Get a specific project's remote source location settings for shared repository according to the Project Id.

        Args:
            project_id (int):

        Returns:
            :obj:`CxSharedRemoteSourceSettingsResponse`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        shared_source_setting = None
        self.remote_settings_shared_url = self.remote_settings_shared_url.format(id=project_id)
        r = requests.get(url=self.remote_settings_shared_url,
                         headers=AuthenticationAPI.AuthenticationAPI.auth_headers)
        if r.status_code == 200:
            a_dict = r.json()
            shared_source_setting = CxSharedRemoteSourceSettingsResponse.CxSharedRemoteSourceSettingsResponse(
                paths=a_dict.get("paths"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_shared_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return shared_source_setting

    def set_remote_source_settings_to_shared(self, project_id, paths, username, password):
        """
        Set a specific project's remote source location to a shared repository.

        Args:
            project_id (int):
            paths (:obj:`list` of :obj:`str`):
            username (str):
            password (sr):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False

        self.remote_settings_shared_url = self.remote_settings_shared_url.format(id=project_id)
        post_body_data = CxSharedRemoteSourceSettingsRequest.CxSharedRemoteSourceSettingsRequest(
            paths=paths,
            credentials=CxCredential.CxCredential(
                username=username,
                password=password
            )
        ).get_post_data()

        r = requests.post(url=self.remote_settings_shared_url, data=post_body_data,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_settings_to_shared(project_id, paths, username, password)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_remote_source_settings_for_perforce_by_project_id(self, project_id):
        """
        Get a specific project's remote source location settings for Perforce repository according to the Project Id.

        Args:
            project_id (int):

        Returns:
            :obj:`CxPerforceSettings`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO, check, when have perforce environment
        perforce_settings = None

        if project_id:
            self.remote_settings_perforce_url = self.remote_settings_perforce_url.format(id=project_id)

        r = requests.get(
            url=self.remote_settings_perforce_url,
            headers=AuthenticationAPI.AuthenticationAPI.auth_headers
        )

        if r.status_code == 200:
            a_dict = r.json()
            perforce_settings = CxPerforceSettings.CxPerforceSettings(
                uri=CxURI.CxURI(
                    absolute_url=(a_dict.get("uri", {}) or {}).get("absoluteUrl"),
                    port=(a_dict.get("uri", {}) or {}).get("port")
                ),
                paths=a_dict.get("paths"),
                browse_mode=a_dict.get("browseMode"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                )
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_remote_source_settings_for_perforce_by_project_id(project_id)
        else:
            raise UnknownHttpStatusError()

        return perforce_settings

    def set_remote_source_settings_to_perforce(self, project_id, username, password, absolute_url, port, paths,
                                               browse_mode):
        """
        Set a specific project's remote source location to a Perforce repository.

        Args:
            project_id (int):
            username (str):
            password (str):
            absolute_url (str):
            port (int):
            paths (:obj:`list` of :obj:`str`):
            browse_mode (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO, check, when have perforce environment

        is_successful = False

        if project_id:
            self.remote_settings_perforce_url = self.remote_settings_perforce_url.format(id=project_id)

        post_data = CxPerforceSettings.CxPerforceSettings(
            credentials=CxCredential.CxCredential(
                username=username,
                password=password,
            ),
            uri=CxURI.CxURI(
                absolute_url=absolute_url,
                port=port
            ),
            paths=paths,
            browse_mode=browse_mode
        ).get_post_data()

        r = requests.post(
            url=self.remote_settings_perforce_url,
            headers=AuthenticationAPI.AuthenticationAPI.auth_headers,
            data=post_data
        )
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_settings_to_perforce(project_id, username, password, absolute_url, port, paths,
                                                        browse_mode)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def set_remote_source_setting_to_git_using_ssh(self, project_id, url, branch, private_key_file_path):
        """
        Set a specific project's remote source location to a GIT repository using the SSH protocol

        Args:
            project_id (int):
            url (str):
            branch (str):
            private_key_file_path (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False

        self.remote_settings_git_ssh_url = self.remote_settings_git_ssh_url.format(id=project_id)

        headers = copy.deepcopy(AuthenticationAPI.AuthenticationAPI.auth_headers)

        file_name = Path(private_key_file_path).name

        with open(private_key_file_path, "rb") as a_file:
            file_content = a_file.read()

        m = MultipartEncoder(
            fields={
                "url": url,
                "branch": branch,
                "privateKey": (file_name, file_content, "text/plain")
            }
        )
        headers.update({"Content-Type": m.content_type})

        r = requests.post(url=self.remote_settings_git_ssh_url, headers=headers, data=m)
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_setting_to_git_using_ssh(project_id, url, branch, private_key_file_path)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def set_remote_source_setting_to_svn_using_ssh(self, project_id, absolute_url, port, paths, private_key_file_path):
        """
        Set a specific project's remote source location to a SVN repository which uses the SSH protocol

        Args:
            project_id (int):
            absolute_url (str):
            port (int):
            paths (:obj:`list` of :obj:`str`):
            private_key_file_path (str):

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        # TODO check, when have svn
        self.remote_settings_svn_ssh_url = self.remote_settings_svn_ssh_url.format(id=project_id)

        headers = copy.deepcopy(AuthenticationAPI.AuthenticationAPI.auth_headers)

        file_name = Path(private_key_file_path).name
        m = MultipartEncoder(
            fields={
                "absoluteUrl": absolute_url,
                "port": port,
                "paths": paths,
                "privateKey": (file_name, open(private_key_file_path, "rb"), "text/plain")
            }
        )
        headers.update({"Content-Type": m.content_type})

        r = requests.post(url=self.remote_settings_git_ssh_url, headers=headers, data=m)
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_remote_source_setting_to_svn_using_ssh(project_id, absolute_url, port, paths,
                                                            private_key_file_path)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def upload_source_code_zip_file(self, project_id, zip_file_path):
        """
        Upload a zip file that contains the source code for scanning.

        Args:
            project_id (int):
            zip_file_path (str): absolute file path

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False
        self.attachments_url = self.attachments_url.format(id=project_id)

        headers = copy.deepcopy(AuthenticationAPI.AuthenticationAPI.auth_headers)

        file_name = Path(zip_file_path).name
        m = MultipartEncoder(
            fields={
                "zippedSource": (file_name, open(zip_file_path, 'rb'), "application/zip")
            }
        )
        headers.update({"Content-Type": m.content_type})

        r = requests.post(url=self.attachments_url, headers=headers, data=m)
        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.upload_source_code_zip_file(project_id, zip_file_path)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def set_data_retention_settings_by_project_id(self, project_id, scans_to_keep=10):
        """
        Set the data retention settings according to Project Id.

        Args:
            project_id (int):
            scans_to_keep (int): number of scans to keep

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        is_successful = False

        self.data_retention_settings_url = self.data_retention_settings_url.format(id=project_id)

        post_body = json.dumps(
            {
                "scansToKeep": scans_to_keep
            }
        )

        r = requests.post(url=self.data_retention_settings_url, data=post_body,
                          headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_data_retention_settings_by_project_id(project_id, scans_to_keep)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def set_issue_tracking_system_as_jira_by_id(self, project_id, issue_tracking_system_id, jira_project_id,
                                                issue_type_id, jira_fields):
        """
        Set a specific issue tracking system as Jira according to Project Id.

        Args:
            project_id (int):
            issue_tracking_system_id (int):
            jira_project_id (str):
            issue_type_id (str):
            jira_fields (:obj:`list` of :obj:`CxIssueTrackingSystemJiraField`)

        Returns:
            bool

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        # TODO, when have jira

        is_successful = False

        if project_id:
            self.jira_url = self.jira_url.format(id=project_id)
        post_data = CxIssueTrackingSystemJira.CxIssueTrackingSystemJira(
            issue_tracking_system_id=issue_tracking_system_id,
            jira_project_id=jira_project_id,
            issue_type_id=issue_type_id,
            fields=jira_fields
        ).get_post_data()

        r = requests.post(
            url=self.jira_url,
            headers=AuthenticationAPI.AuthenticationAPI.auth_headers,
            data=post_data
        )

        if r.status_code == 204:
            is_successful = True
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.set_issue_tracking_system_as_jira_by_id(project_id, issue_tracking_system_id, jira_project_id,
                                                         issue_type_id, jira_fields)
        else:
            raise UnknownHttpStatusError()

        return is_successful

    def get_all_preset_details(self):
        """
        get details of all presets

        Returns:
            :obj:`list` of :obj:`CxPreset`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError

        """
        all_preset_details = []
        r = requests.get(url=self.presets_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_list = r.json()
            all_preset_details = [
                CxPreset.CxPreset(
                    preset_id=item.get("id"),
                    name=item.get("name"),
                    owner_name=item.get("ownerName"),
                    link=CxLink.CxLink(
                        rel=(item.get("link", {}) or {}).get("rel"),
                        uri=(item.get("link", {}) or {}).get("uri")
                    )
                ) for item in a_list
            ]
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_all_preset_details()
        else:
            raise UnknownHttpStatusError()

        return all_preset_details

    def get_preset_id_by_name(self, preset_name):
        """

        Args:
            preset_name (str):

        Returns:
            int: preset id
        """
        all_presets = self.get_all_preset_details()
        a_dict_preset_name_id = {item.name: item.id for item in all_presets}
        return a_dict_preset_name_id.get(preset_name)

    def get_preset_details_by_preset_id(self, preset_id):
        """
        Get details of a specified preset by Id.

        Args:
            preset_id (int):

        Returns:
            :obj:`CxPreset`

        Raises:
            BadRequestError
            NotFoundError
            UnknownHttpStatusError
        """
        preset = None
        self.preset_url = self.preset_url.format(id=preset_id)

        r = requests.get(url=self.preset_url, headers=AuthenticationAPI.AuthenticationAPI.auth_headers)

        if r.status_code == 200:
            a_dict = r.json()
            preset = CxPreset.CxPreset(
                preset_id=a_dict.get("id"),
                name=a_dict.get("name"),
                owner_name=a_dict.get("ownerName"),
                link=CxLink.CxLink(
                    rel=(a_dict.get("link", {}) or {}).get("rel"),
                    uri=(a_dict.get("link", {}) or {}).get("uri")
                ),
                query_ids=a_dict.get("queryIds")
            )
        elif r.status_code == http.HTTPStatus.BAD_REQUEST:
            raise BadRequestError(r.text)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            raise NotFoundError()
        elif (r.status_code == http.HTTPStatus.UNAUTHORIZED) and (self.retry < self.max_try):
            AuthenticationAPI.AuthenticationAPI.reset_auth_headers()
            self.retry += 1
            self.get_preset_details_by_preset_id(preset_id)
        else:
            raise UnknownHttpStatusError()

        return preset